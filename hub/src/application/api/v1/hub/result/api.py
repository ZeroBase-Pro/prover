from utils.router import hub_blueprint
from utils.util import http_response
from utils.constant import API_LOGGER
from utils.constant import HttpStatus
from utils.constant import PRIVATE_KEY, PUBLIC_KEY
from utils.constant import GRPC_STATUS_ERROR
import asyncio

from sanic.request import Request
from sanic_ext import validate

from . import serializers

import logging
import aiofiles
import os

from config import Config

from modules.explorer import Explorer
from modules.encryptor import RSAEncryption

from typing import List

config = Config()
logger = logging.getLogger(API_LOGGER)

async def get_explorer():
    try:
        async with aiofiles.open(config.Explorer.key_path, mode='r') as file:
            key = await file.read()
    except FileNotFoundError:
        logger.error("[API] - key file not found")
        response = serializers.PostResultPrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    
    rsa_encryption = RSAEncryption(public_key=key)
    explorer = Explorer(config.Explorer.api, rsa_encryption)
    return explorer

@hub_blueprint.post("/result")
@validate(json=serializers.PostResultRequest)
async def hub_post_results(request: Request, body: serializers.PostResultRequest):
    private_key_path = os.path.join(config.Env.session_keys_path, PRIVATE_KEY)
    try:
        async with aiofiles.open(private_key_path, mode='r') as file:
            private_key = await file.read()
    except FileNotFoundError:
        logger.error("[API] - Private key file not found")
        response = serializers.PostResultPrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    
    rsa_encryption = RSAEncryption(private_key=private_key)
    
    # Decrypt
    try:
        project_name = rsa_encryption.decrypt(body.project_name)
        proof_hash = rsa_encryption.decrypt(body.proof_hash)
        verifiers = rsa_encryption.decrypt(body.verifiers)
        duration = rsa_encryption.decrypt(body.duration)
    except Exception as e:
        logger.error(f"[API] - Decryption failed: {e}")
        response = serializers.PostResultDecryptionFailedResponse().model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
        
    if not project_name or not proof_hash or not verifiers or not duration:
        logger.error("[API] - Decryption returned empty data")
        response = serializers.PostResultDecryptionFailedResponse().model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
    
    explorer = await get_explorer()
    await explorer.send_proof(project_name, proof_hash, duration, verifiers)
    
    response = serializers.PostResultSuccessfullyResponse().model_dump()
    return http_response(status=HttpStatus.OK, **response)

