import aiofiles
import ujson
import grpc
import time
import os

from config import Config

from . import prove_service_pb2
from . import prove_service_pb2_grpc

from modules.prove_service.v1 import ProveServiceV1, ProofResult
from modules.hub import Hub
from modules.proof_manager import ProofManager
from modules.encryptor import RSAEncryption

from utils.constant import STATUS_CODE_PRIVATE_KEY_INVALID, STATUS_CODE_PRIVATE_KEY_NOT_FOUND
from utils.constant import OAUTH_PROVIDER_GOOGLE
from utils.constant import TASK_TYPE_ZKLOGIN
from utils.constant import PRIVATE_KEY
from utils.constant import STATUS_CODE_SUCCESSFULLY, STATUS_CODE_ERROR

class ProveService(prove_service_pb2_grpc.ProveServiceServicer):

    def __init__(self, prove_service: ProveServiceV1, proof_manager:ProofManager, hub: Hub):
        """
        Initialize GrpcServer with dependency injection.

        Args:
            prove_service (ProveService): An instance of ProveService to handle proof generation logic.
        """
        self.prove_service = prove_service
        self.proof_manager = proof_manager
        self.hub = hub
        self.config = Config()

    async def ProveNosha256(self, request:prove_service_pb2.ProveNosha256Request, context:grpc.aio.ServicerContext):
        """
        Handle the ProveNosha256 request to generate proof data without SHA256.

        Args:
            request (ProveNosha256Request): The request object containing base request info and length.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            ProveNosha256Response: The response object containing status and proof data.
        """
        # Extract base request parameters and length
        base_request = request.base_request
        prover_id = base_request.prover_id
        circuit_template_id = base_request.circuit_template_id
        input_data = base_request.input_data
        is_encrypted = base_request.is_encrypted
        auth_token = base_request.auth_token
        length = request.length  # Length of the input data

        method = request.method or TASK_TYPE_ZKLOGIN
        oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

        proof_hash = request.proof_hash

        ok, msg = self.proof_manager.claim_task(proof_hash)
        if ok != True:
            return prove_service_pb2.ProveNosha256Response(
                base_response=prove_service_pb2.StatusResponse(
                    code=ok,
                    msg=msg
                ),
            )        

        proof_result: ProofResult = await self.prove_service.prove_nosha256(method, prover_id, circuit_template_id, input_data, is_encrypted, auth_token, length, oauth_provider)
        
        if proof_result.project_name:
            await self.hub.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

        return prove_service_pb2.ProveNosha256Response(
            base_response=prove_service_pb2.StatusResponse(
                code=proof_result.code,
                msg=proof_result.msg
            ),
            proof_data=proof_result.proof,
        )

    async def ProveNosha256WithWitness(self, request:prove_service_pb2.ProveNosha256WithWitnessRequest, context:grpc.aio.ServicerContext):
        """
        Handle the ProveNosha256WithWitness request to generate proof and witness data without SHA256.

        Args:
            request (ProveNosha256WithWitnessRequest): The request object containing base request info and length.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            ProveNosha256WithWitnessResponse: The response object containing status, proof, and witness data.
        """
        # Extract base request parameters and length
        base_request = request.base_request
        prover_id = base_request.prover_id
        circuit_template_id = base_request.circuit_template_id
        input_data = base_request.input_data
        is_encrypted = base_request.is_encrypted
        auth_token = base_request.auth_token
        length = request.length

        method = request.method or TASK_TYPE_ZKLOGIN
        oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

        proof_hash = request.proof_hash

        ok, msg = self.proof_manager.claim_task(proof_hash)
        if ok != True:
            return prove_service_pb2.ProveNosha256WithWitnessResponse(
                base_response=prove_service_pb2.StatusResponse(
                    code=ok,
                    msg=msg
                ),
            )
                
        proof_result: ProofResult = await self.prove_service.prove_nosha256_with_witness(method, prover_id, circuit_template_id, input_data, is_encrypted, auth_token, length, oauth_provider)
        
        if proof_result.project_name:
            await self.hub.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

        return prove_service_pb2.ProveNosha256WithWitnessResponse(
            base_response=prove_service_pb2.StatusResponse(
                code=proof_result.code,
                msg=proof_result.msg
            ),
            proof_data=proof_result.proof,
            witness_data=proof_result.witness
        )
    
    

    async def ProveNosha256Offchain(self, request:prove_service_pb2.ProveNosha256OffchainRequest, context:grpc.aio.ServicerContext):
        """
        Handle the ProveNosha256Offchain request to generate proof and witness data for off-chain verification.

        Args:
            request (ProveNosha256OffchainRequest): The request object containing base request info and length.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            ProveNosha256OffchainResponse: The response object containing status, proof, and witness data.
        """
        # Extract base request parameters and length
        base_request = request.base_request
        prover_id = base_request.prover_id
        circuit_template_id = base_request.circuit_template_id
        input_data = base_request.input_data
        is_encrypted = base_request.is_encrypted
        auth_token = base_request.auth_token
        length = request.length

        method = request.method or TASK_TYPE_ZKLOGIN
        oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

        proof_hash = request.proof_hash

        ok, msg = self.proof_manager.claim_task(proof_hash)
        if ok != True:
            return prove_service_pb2.ProveNosha256OffchainResponse(
                base_response=prove_service_pb2.StatusResponse(
                    code=ok,
                    msg=msg
                ),
            )

        proof_result: ProofResult = await self.prove_service.prove_nosha256_offchain(method, prover_id, circuit_template_id, input_data, is_encrypted, auth_token, length, oauth_provider)
        
        if proof_result.project_name:
            await self.hub.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

        return prove_service_pb2.ProveOffchainResponse(
            base_response=prove_service_pb2.StatusResponse(
                code=proof_result.code,
                msg=proof_result.msg
            ),
            proof_data=proof_result.proof,
            witness_data=proof_result.witness
        )

    async def GetPublicKey(self, request:prove_service_pb2.GetPublicKeyResponse, context:grpc.aio.ServicerContext):
        """
        Handle the GetPublicKey request to return the public key.

        Args:
            request (Empty): An empty request.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            GetPublicKeyResponse: The response object containing status and public key.
        """
        prove_code, msg, public_key = await self.prove_service.get_public_key()

        return prove_service_pb2.GetPublicKeyResponse(
            base_response=prove_service_pb2.StatusResponse(
                code=prove_code,
                msg=msg
            ),
            public_key=public_key
        )
    
    '''
    async def Ping(self, request, context):
        start_time = time.perf_counter()  # Start timer

        prover_id = request.prover_id

        if prover_id == "circom":
            prover_instance = CircomProve(Config.CircomAddress)
            prove_code, msg, running_count = await prover_instance.get_running_prove_tasks()
        else:
            end_time = time.perf_counter()  # End timer
            logger.info(f"[Ping] took {end_time - start_time:.4f} seconds")
            return prove_service_pb2.PingResponse(
                base_response=prove_service_pb2.StatusResponse(
                    code=RPC_STATUS_ERROR,
                    msg="Prover not match"
                ),
                running_count=0
            )

        logger.info(f"[Ping] took {end_time - start_time:.4f} seconds")
        return prove_service_pb2.PingResponse(
                base_response=prove_service_pb2.StatusResponse(
                    code=prove_code,
                    msg=msg
                ),
                running_count=running_count
            )
    '''

    async def UpdateVerifier(self, request:prove_service_pb2.UpdateVerifierRequest, context:grpc.aio.ServicerContext):
        """
        Handle the Ping request for health checks or to keep the connection alive.

        Args:
            request (Empty): An empty request.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            Empty: An empty response.
        """
        proof_hash = request.proof_hash
        verifiers = request.verifier

        private_key_path = os.path.join(self.config.Env.crypto_keys_path, PRIVATE_KEY)

        try:
            async with aiofiles.open(private_key_path, mode='r') as file:
                private_key = await file.read()
        except FileNotFoundError:
            return prove_service_pb2.UpdateVerifierResponse(base_response=prove_service_pb2.StatusResponse(
                code=STATUS_CODE_PRIVATE_KEY_NOT_FOUND,
                msg="Private key file not found"
            ))

        # Decrypt the input data using RSA
        rsa_encryption = RSAEncryption(private_key=private_key)
        try:
            proof_hash = rsa_encryption.decrypt(proof_hash)
            verifiers = ujson.loads(rsa_encryption.decrypt(verifiers))
        except:
            return prove_service_pb2.UpdateVerifierResponse(base_response=prove_service_pb2.StatusResponse(
                code=STATUS_CODE_PRIVATE_KEY_INVALID,
                msg="Decryption failed with provided private key: invalid input data"
            ))
        if not verifiers:
            return prove_service_pb2.UpdateVerifierResponse(base_response=prove_service_pb2.StatusResponse(
                code=STATUS_CODE_PRIVATE_KEY_INVALID,
                msg="Decryption failed with provided private key: no verifiers found"
            ))

        result = await self.hub.update_verifier(proof_hash, verifiers)
        if result:
            return prove_service_pb2.UpdateVerifierResponse(base_response=prove_service_pb2.StatusResponse(
                code=STATUS_CODE_SUCCESSFULLY,
                msg="Successfully."
            ))
        else:
            return prove_service_pb2.UpdateVerifierResponse(base_response=prove_service_pb2.StatusResponse(
                code=STATUS_CODE_ERROR,
                msg="Update failed."
            ))

    async def Ping(self, request:prove_service_pb2.Empty, context:grpc.aio.ServicerContext):
        """
        Handle the Ping request for health checks or to keep the connection alive.

        Args:
            request (Empty): An empty request.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            Empty: An empty response.
        """
        await self.prove_service.ping()
        return prove_service_pb2.Empty()

def create_grpc_prover_service(server: grpc.Server, prove_service: ProveServiceV1, proof_manager:ProofManager, hub: Hub):
    """
    Start the gRPC server and listen on the specified host and port.

    Args:
        host (str): Host to bind the gRPC server to.
        port (int): Port to bind the gRPC server to.
        prove_service (ProveService): The ProveService instance to inject into the GrpcServer.

    Returns:
        grpc.aio.Server: The configured gRPC server.
    """
    # Add the ProveService to the server with dependency injection
    service = ProveService(prove_service, proof_manager, hub)
    prove_service_pb2_grpc.add_ProveServiceServicer_to_server(service, server)
    # Bind the server to the specified address and port

    return server