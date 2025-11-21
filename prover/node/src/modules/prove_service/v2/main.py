import os
import logging
import aiofiles
import time
from typing import Tuple, Optional, Dict, List
import threading
import ujson

from modules.project_manager import ProjectManager
from modules.prover.circom import CircomProver, CircomResultV2
from modules.prover.gnark import PrivateProver
from modules.encryptor import RSAEncryption
from modules.oauth_provider import OAuthProvider, OAuthProviderResolver

from config import SampleConfig
from utils.constant import PROVER_CIRCOM, PROVER_PRIVATE
from utils.constant import TASK_TYPE_ZKLOGIN, TASK_TYPE_TIGA
from utils.constant import PUBLIC_KEY, PRIVATE_KEY
from utils.constant import STATUS_CODE_PRIVATE_KEY_INVALID, STATUS_CODE_PRIVATE_KEY_NOT_FOUND, STATUS_CODE_PUBLIC_KEY_NOT_FOUND, STATUS_CODE_PUBLIC_KEY_INVALID
from utils.constant import STATUS_CODE_UNAUTHORIZED_PAYLOAD
from utils.constant import STATUS_CODE_UNSUPPORT_TASK_TYPE, STATUS_CODE_UNSUPPORT_PROVER, STATUS_CODE_UNSUPPORT_OAUTH_PROVIDER
from utils.constant import STATUS_CODE_SUCCESSFULLY, STATUS_CODE_ERROR

from dataclasses import dataclass, field

@dataclass
class ProofResult:
    code: int
    msg: str
    proof: Optional[str] = None
    proof_solidity: Optional[str] = None
    proof_bytes: Optional[bytes] = None
    public_witness: Optional[str] = None
    public_witness_bytes: Optional[bytes] = None
    project_name: Optional[str] = None
    verifiers: List[str] = field(default_factory=list)
    duration: Optional[float] = None
        
class ProveServiceV2:
    _instance = None
    _locker = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(ProveServiceV2, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_manager: ProjectManager, oauth_provider: Dict[str, OAuthProvider], oauth_provider_resolver: OAuthProviderResolver, config: SampleConfig):
        if self._initialized:
            return
        
        self.project_manager = project_manager
        self.oauth_provider = oauth_provider
        self.oauth_provider_resolver = oauth_provider_resolver
        self.config = config

        self._initialized = True

    async def _process_input(self, input_data: str, is_encrypted: bool) -> Tuple[Optional[str], Optional[str]]:
        start_time = time.perf_counter()  # Start timer
        """
        Process the input data, decrypting if necessary.

        Args:
            input_data (str): The user's input data, possibly encrypted.
            is_encrypted (bool): Indicates if the input data is encrypted.

        Returns:
            tuple: (Processed input data, Error message if any)
        """
        private_key_path = os.path.join(self.config.Env.crypto_keys_path, PRIVATE_KEY)
        if is_encrypted:
            try:
                # Asynchronously read the private key file
                async with aiofiles.open(private_key_path, mode='r') as file:
                    private_key = await file.read()
            except FileNotFoundError:
                logging.error("[process_input] - Private key file not found")
                end_time = time.perf_counter()  # End timer
                logging.info(f"[process_input] took {end_time - start_time:.4f} seconds")
                return STATUS_CODE_PRIVATE_KEY_NOT_FOUND, "Private key file not found"

            # Decrypt the input data using RSA
            rsa_encryption = RSAEncryption(private_key=private_key)
            input_data = rsa_encryption.decrypt(input_data)
            if not input_data:
                logging.error("[process_input] - Decryption failed with provided private key")
                end_time = time.perf_counter()  # End timer
                logging.info(f"[process_input] took {end_time - start_time:.4f} seconds")
                return STATUS_CODE_PRIVATE_KEY_INVALID, "Decryption failed with provided private key"
        end_time = time.perf_counter()  # End timer
        logging.info(f"[process_input] took {end_time - start_time:.4f} seconds")
        return True, input_data
    
    async def _validate_task_type_and_input(
        self,
        task_type: int,
        circuit_template_id: str,
        input_data: str,
        oauth_provider: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Validates method and input data according to the proving method.

        Returns:
            A tuple of (bool, msg). If validation passes, bool is true.
        """
        if task_type == TASK_TYPE_ZKLOGIN:
            specify_provider = self.oauth_provider_resolver.resolve_provider(circuit_template_id)
            if specify_provider:
                oauth_provider = specify_provider
                
            oauth_provider_cls: Optional[OAuthProvider] = self.oauth_provider.get(oauth_provider, None)
            if not oauth_provider_cls:
                return STATUS_CODE_UNSUPPORT_OAUTH_PROVIDER, f"OAuth provider '{oauth_provider}' not found"
            if not await oauth_provider_cls.verify(input_data):
                return STATUS_CODE_UNAUTHORIZED_PAYLOAD, "Verification failed due to invalid input data"

        elif task_type == TASK_TYPE_TIGA:
            if circuit_template_id == "10006" or circuit_template_id == "10005" or circuit_template_id == "10010":
                return True, None
            if ujson.loads(input_data).setdefault('modules', None):
                return STATUS_CODE_UNAUTHORIZED_PAYLOAD, "Data is invalid, please check the input data"

        else:
            return STATUS_CODE_UNSUPPORT_TASK_TYPE, f"Task '{task_type}' is not supported. Please choose a supported method"
        
        return True, None

    async def prove(
        self,
        method: int,
        prover_id: str,
        circuit_template_id: str,
        input_data: str,
        is_encrypted: bool, 
        auth_token: str,
        length: int,
        oauth_provider: str
    ) -> Tuple[int, str, Optional[str]]:
        start_time = time.perf_counter()
        
        ok, msg = await self._process_input(input_data, is_encrypted)
        if ok != True:
            return ProofResult(
                code=ok,
                msg=msg
            )
            
        ok, msg = await self._validate_task_type_and_input(method, circuit_template_id, input_data, oauth_provider)
        if ok != True:
            return ProofResult(
                code=ok,
                msg=msg
            )
            
        try:
            if prover_id == PROVER_CIRCOM:
                prover_instance = CircomProver(self.config.Prover.Circom.address)
                prover_result = await prover_instance.prove_v2(input_data, circuit_template_id, length)
            elif prover_id == PROVER_PRIVATE:
                private_prover = PrivateProver(self.config.Prover.Private.address)
                rpc_map = {
                    "10005": private_prover.prove_tiga_offchain,
                    "10006": private_prover.prove_binance_offchain,
                    "10010": private_prover.prove_merkle_offchain,
                }
                rpc_func = rpc_map.get(circuit_template_id)
                if not rpc_func:
                    logging.info(f"[v2] - [prove] Unsupported circuit_template_id: {circuit_template_id}")
                    return ProofResult(
                        code=STATUS_CODE_UNSUPPORT_TASK_TYPE,
                        msg=f"Unsupported circuit_template_id: {circuit_template_id}"
                    )
                
                prover_result = await rpc_func(input_data, circuit_template_id)

            else:
                logging.info(f"[v2] - [prove] took {time.perf_counter() - start_time:.4f} seconds")
                return ProofResult(
                    code=STATUS_CODE_UNSUPPORT_PROVER,
                    msg="Prover not match"
                )
        except NotImplementedError as e:
            return ProofResult(
                    code=STATUS_CODE_ERROR,
                    msg=str(e)
                )

        if prover_result.code == STATUS_CODE_SUCCESSFULLY:
            logging.info("[v2] - [prove] - Successfully")
        else:
            logging.error(f"[v2] - [prove] - Error, Reason: {prover_result.msg}")
        
        logging.info(f"[v2] - [prove] took {time.perf_counter() - start_time:.4f} seconds")
        end_time = time.perf_counter()  # End timer
        
        project_name = None
        verifiers = []
        duration = None
 
        if prover_result.proof:
            project = self.project_manager.get_project(ujson.loads(prover_result.public_witness)[-1])
            project_name = project["project_name"]
            verifiers = project["verifiers"]
            duration = int((end_time - start_time) * 1000)
        
        return ProofResult(
                code=prover_result.code,
                msg=prover_result.msg,
                proof=prover_result.proof,
                proof_solidity=prover_result.proof_solidity,
                proof_bytes=prover_result.proof_bytes,
                public_witness=prover_result.public_witness,
                public_witness_bytes=prover_result.public_witness_bytes,
                project_name=project_name,
                verifiers=verifiers,
                duration=duration
            )