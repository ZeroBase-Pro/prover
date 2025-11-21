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
from modules.prove_service.v2 import ProveServiceV2, ProofResult

from modules.oauth_provider import OAuthProviderResolver
from modules.oauth_provider import google
from modules.oauth_provider import telegram
from modules.oauth_provider import x509_google


from fastapi import FastAPI, Depends, APIRouter
from utils.error_util import HTTPException

from fastapi.middleware.cors import CORSMiddleware

# Define your configuration dependency


def get_prove_service() -> ProveServiceV2:
    oauth_provider = {}
    config = Config()
    oauth_provider[OAUTH_PROVIDER_GOOGLE] = google.Provider(config.OauthProvider.Google.api, config.OauthProvider.Google.circom_bigint_n, config.OauthProvider.Google.circom_bigint_k)
    oauth_provider[OAUTH_PROVIDER_TELEGRAM] = telegram.Provider(config.OauthProvider.Telegram.api, config.OauthProvider.Telegram.circom_bigint_n, config.OauthProvider.Telegram.circom_bigint_k)
    oauth_provider[OAUTH_PROVIDER_X509_GOOGLE] = x509_google.Provider(config.OauthProvider.X509Google.api, config.OauthProvider.X509Google.circom_bigint_n, config.OauthProvider.X509Google.circom_bigint_k)
    oauth_provider_resolver = OAuthProviderResolver(config.Env.oauth_provider_resolver_path)
    project_manager = ProjectManager(config.Env.project_path)
    return ProveServiceV2(project_manager, oauth_provider, oauth_provider_resolver, config)

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

prove_service_dependency = Annotated[ProveServiceV2, Depends(get_prove_service)]
encryptor_dependency = Annotated[RSAEncryption, Depends(get_encryptor)]
proof_manager_dependency = Annotated[ProofManager, Depends(get_proof_manager)]
hub_dependency = Annotated[Hub, Depends(get_hub)]
config_dependency = Annotated[SampleConfig, Depends(get_config)]

@router.post("/api/v2/prove", response_model=serializers.ProveV2Response)
async def prove(request: serializers.ProveV2Request, prove_service_cls: prove_service_dependency, proof_manager_cls: proof_manager_dependency, hub_cls: hub_dependency):
    # Extract base request parameters
    prover = request.prover                   # Identifier for the prover
    circuit_template_id = request.circuit_template_id  # Circuit template identifier
    payload = request.payload
    is_encrypted = request.is_encrypted             # Indicates if input data is encrypted
    auth_token = request.auth_token                 # Authentication token
    task_type = request.task_type or TASK_TYPE_ZKLOGIN
    length = request.length
    oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

    proof_hash = request.proof_hash
    
    ok, msg = proof_manager_cls.claim_task(proof_hash)
    if ok != True:
        raise HTTPException(code=ok, msg=msg, status_code=500)

    proof_result: ProofResult = await prove_service_cls.prove(task_type, prover, circuit_template_id, payload, is_encrypted, auth_token, length, oauth_provider)
        
    if proof_result.project_name:
        await hub_cls.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)
            
    return serializers.ProveV2Response(
        code=proof_result.code,
        msg=proof_result.msg,
        proof=proof_result.proof,
        proof_solidity=proof_result.proof_solidity,
        proof_bytes=proof_result.proof_bytes,
        public_witness=proof_result.public_witness,
        public_witness_bytes=proof_result.public_witness_bytes
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