from typing import  Annotated

import logging
import os
import aiofiles
import ujson

from . import serializers

from config import Config, SampleConfig
from utils.constant import TASK_TYPE_ZKLOGIN
from utils.constant import OAUTH_PROVIDER_GOOGLE, OAUTH_PROVIDER_TELEGRAM, OAUTH_PROVIDER_X509_GOOGLE
from utils.constant import PRIVATE_KEY
from utils.constant import TASK_STATUS_PENGDING
from utils.constant import STATUS_CODE_SUCCESSFULLY, STATUS_CODE_ERROR
from utils.constant import STATUS_CODE_PRIVATE_KEY_INVALID, STATUS_CODE_PRIVATE_KEY_NOT_FOUND
from modules.encryptor import RSAEncryption
from modules.proof_manager import ProofManager
from modules.project_manager import ProjectManager
from modules.hub import Hub
from modules.prove_service.v1 import ProveServiceV1, ProofResult

from modules.oauth_provider import OAuthProviderResolver
from modules.oauth_provider import google
from modules.oauth_provider import telegram
from modules.oauth_provider import x509_google


from fastapi import FastAPI, HTTPException, Depends, APIRouter

from fastapi.middleware.cors import CORSMiddleware

# Define your configuration dependency


def get_prove_service() -> ProveServiceV1:
    oauth_provider = {}
    config = Config()
    oauth_provider[OAUTH_PROVIDER_GOOGLE] = google.Provider(config.OauthProvider.Google.api, config.OauthProvider.Google.circom_bigint_n, config.OauthProvider.Google.circom_bigint_k)
    # oauth_provider[OAUTH_PROVIDER_TELEGRAM] = telegram.Provider(config.OauthProvider.Telegram.api, config.OauthProvider.Telegram.circom_bigint_n, config.OauthProvider.Telegram.circom_bigint_k)
    oauth_provider[OAUTH_PROVIDER_X509_GOOGLE] = x509_google.Provider(config.OauthProvider.X509Google.api, config.OauthProvider.X509Google.circom_bigint_n, config.OauthProvider.X509Google.circom_bigint_k)
    oauth_provider_resolver = OAuthProviderResolver(config.Env.oauth_provider_resolver_path)
    project_manager = ProjectManager(config.Env.project_path)
    return ProveServiceV1(project_manager, oauth_provider, oauth_provider_resolver, config)

def get_encryptor() -> RSAEncryption:
    config = Config()
    try: 
        with open(config.Env.session_keys_path, mode='r') as file:
            session_key = file.read()
    except FileNotFoundError:
        logging.error("[API] - Public key file not found")
        return
    encrytor = RSAEncryption(public_key=session_key)
    return encrytor

def get_proof_manager() -> ProofManager:
    config = Config()
    proof_manager = ProofManager(config.Env.cache_path)
    return proof_manager

def get_hub() -> Hub:
    config = Config()
    hub = Hub(config.Hub.API, config.Env.session_keys_path, config)
    return hub

def get_config() -> SampleConfig:
    config = Config()
    return config


router = APIRouter()

@router.get("/ping", response_model=serializers.PingResponse)
async def ping():
    """
    Simple ping endpoint for basic connectivity check
    """
    return serializers.PingResponse(code=0, msg="Pong")

prove_service_dependency = Annotated[ProveServiceV1, Depends(get_prove_service)]
encryptor_dependency = Annotated[RSAEncryption, Depends(get_encryptor)]
proof_manager_dependency = Annotated[ProofManager, Depends(get_proof_manager)]
hub_dependency = Annotated[Hub, Depends(get_hub)]
config_dependency = Annotated[SampleConfig, Depends(get_config)]

@router.post("/prove", response_model=serializers.ProveResponse)
async def prove(request: serializers.ProveRequest, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    prover_id = request.prover_id
    circuit_template_id = request.circuit_template_id
    input_data = request.input_data
    is_encrypted = request.is_encrypted

    method = request.method or TASK_TYPE_ZKLOGIN
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash
    
    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(status_code=400, detail=msg)
    
    proof_result: ProofResult = await prove_service_cls.prove(method, prover_id, circuit_template_id, input_data, is_encrypted, "", oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

    return serializers.ProveResponse(
        code=proof_result.code,
        msg=proof_result.msg,
        proof_data=proof_result.proof 
    )

@router.post("/prove_with_witness", response_model=serializers.ProveWithWitnessResponse)
async def prove_with_witness(request: serializers.ProveWithWitnessRequest, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    prover_id = request.prover_id
    circuit_template_id = request.circuit_template_id
    input_data = request.input_data
    is_encrypted = request.is_encrypted

    method = request.method or TASK_TYPE_ZKLOGIN
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash

    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(status_code=400, detail=msg)
            
    proof_result: ProofResult = await prove_service_cls.prove_nosha256_with_witness(method, prover_id, circuit_template_id, input_data, is_encrypted, "", oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

    return serializers.ProveWithWitnessResponse(
        code=proof_result.code,
        msg=proof_result.msg,
        proof_data=proof_result.proof,
        witness_data=proof_result.witness
    )

@router.post("/prove_offchain", response_model=serializers.ProveWithWitnessResponse)
async def prove_offchain(request: serializers.ProveWithWitnessRequest, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    prover_id = request.prover_id
    circuit_template_id = request.circuit_template_id
    input_data = request.input_data
    is_encrypted = request.is_encrypted

    method = request.method or TASK_TYPE_ZKLOGIN
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash

    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(status_code=400, detail=msg)
            
    proof_result: ProofResult = await prove_service_cls.prove_offchain(method, prover_id, circuit_template_id, input_data, is_encrypted, "", oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

    return serializers.ProveOffchainResponse(
        code=proof_result.code,
        msg=proof_result.msg,
        proof_data=proof_result.proof,
        witness_data=proof_result.witness
    )

@router.post("/prove_nosha256", response_model=serializers.ProveNosha256Response)
async def prove_nosha256(request: serializers.ProveNosha256Request, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    prover_id = request.prover_id
    circuit_template_id = request.circuit_template_id
    input_data = request.input_data
    is_encrypted = request.is_encrypted
    length = request.length

    method = request.method or TASK_TYPE_ZKLOGIN
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash

    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(status_code=400, detail=msg)
                
    proof_result: ProofResult = await prove_service_cls.prove_nosha256(method, prover_id, circuit_template_id, input_data, is_encrypted, "", length, oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

    return serializers.ProveNosha256Response(
        code=proof_result.code,
        msg=proof_result.msg,
        proof_data=proof_result.proof,
    )

@router.post("/prove_nosha256_with_witness", response_model=serializers.ProveNosha256WithWitnessResponse)
async def prove_nosha256_with_witness(request: serializers.ProveNosha256WithWitnessRequest, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    prover_id = request.prover_id
    circuit_template_id = request.circuit_template_id
    input_data = request.input_data
    is_encrypted = request.is_encrypted
    length = request.length

    method = request.method or TASK_TYPE_ZKLOGIN
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash

    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(status_code=400, detail=msg)

    proof_result: ProofResult = await prove_service_cls.prove_nosha256_with_witness(method, prover_id, circuit_template_id, input_data, is_encrypted, "", length, oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

    return serializers.ProveNosha256Response(
        code=proof_result.code,
        msg=proof_result.msg,
        proof_data=proof_result.proof,
        witness_data=proof_result.witness
    )


@router.post("/prove_nosha256_offchain", response_model=serializers.ProveNosha256OffchainResponse)
async def prove_nosha256_offchain(request: serializers.ProveNosha256OffchainRequest, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    prover_id = request.prover_id
    circuit_template_id = request.circuit_template_id
    input_data = request.input_data
    is_encrypted = request.is_encrypted
    length = request.length

    method = request.method or TASK_TYPE_ZKLOGIN
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash

    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(status_code=400, detail=msg)
            
    proof_result: ProofResult = await prove_service_cls.prove_nosha256_offchain(method, prover_id, circuit_template_id, input_data, is_encrypted, "", length, oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

    return serializers.ProveNosha256OffchainResponse(
        code=proof_result.code,
        msg=proof_result.msg,
        proof_data=proof_result.proof,
        witness_data=proof_result.witness
    )

@router.get("/get_public_key", response_model=serializers.GetPublicKeyResponse)
async def get_public_key(prove_service_cls: prove_service_dependency):
    prove_code, msg, public_key = await prove_service_cls.get_public_key()
    return serializers.GetPublicKeyResponse(
        code=prove_code,
        msg=msg,
        public_key=public_key or ""
    )

@router.get("/ping", response_model=serializers.StatusResponse)
async def ping(prove_service_cls: prove_service_dependency):
    prove_code, msg = await prove_service_cls.ping()
    return serializers.StatusResponse(
        code=prove_code,
        msg=msg
    )

@router.put("/verifier", response_model=serializers.StatusResponse)
async def verifier(request: serializers.UpdateVerifierRequest, hub_cls: hub_dependency, config_cls: config_dependency):
    proof_hash = request.proof_hash
    verifiers = request.verifier


    private_key_path = os.path.join(config_cls.Env.crypto_keys_path, PRIVATE_KEY)

    try:
        async with aiofiles.open(private_key_path, mode='r') as file:
            private_key = await file.read()
    except FileNotFoundError:
        return serializers.StatusResponse(code=STATUS_CODE_PRIVATE_KEY_NOT_FOUND, msg="Private key file not found")

    # Decrypt the input data using RSA
    rsa_encryption = RSAEncryption(private_key=private_key)
    try:
        proof_hash = rsa_encryption.decrypt(proof_hash)
        verifiers = ujson.loads(rsa_encryption.decrypt(verifiers))
    except:
        return serializers.StatusResponse(code=STATUS_CODE_PRIVATE_KEY_INVALID, msg="Decryption failed with provided private key")
    if not verifiers:
        return serializers.StatusResponse(code=STATUS_CODE_PRIVATE_KEY_INVALID, msg="Decryption failed with provided private key")

    result = await hub_cls.update_verifier(proof_hash, verifiers)
    if result:
        return serializers.StatusResponse(code=STATUS_CODE_SUCCESSFULLY, msg="Successfully")
    else:
        return serializers.StatusResponse(code=STATUS_CODE_ERROR, msg="Update failed")

@router.post("/push_task", response_model=serializers.StatusResponse)
async def push_task(request: serializers.PushTaskRequest, encryptor: encryptor_dependency, proof_manager_cls: proof_manager_dependency):
    proof_hash = request.proof_hash
    signature = request.signature

    if not encryptor.verify(proof_hash, signature):
        raise HTTPException(status_code=400, detail="invalid signature")
    
    if proof_manager_cls.get(proof_hash):
        raise HTTPException(status_code=400, detail="Proof hash is exist.")
    
    proof_manager_cls.set(proof_hash, TASK_STATUS_PENGDING, 60)
    
    return serializers.StatusResponse(
        code=STATUS_CODE_SUCCESSFULLY,
        msg="Successfully"
    )


def create_http_prover_service(app: FastAPI = FastAPI()) -> FastAPI:
    """
    Initializes and configures the FastAPI server with necessary middlewares and settings.
    """
    
    # Set up CORS (Cross-Origin Resource Sharing) to allow requests from specific origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Modify as needed for specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include the router with all endpoints
    app.include_router(router)

    return app

# Run server if this script is executed directly
if __name__ == "__main__":
    # Initialize the server configuration
    server_app = create_http_prover_service()

    # Start Uvicorn server
    import uvicorn
    uvicorn.run(server_app, host="0.0.0.0", port=8000, log_level="info")