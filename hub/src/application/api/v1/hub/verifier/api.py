from utils.router import hub_blueprint
from utils.util import http_response
from utils.constant import API_LOGGER
from utils.constant import HttpStatus
from utils.constant import PRIVATE_KEY, PUBLIC_KEY
from utils.constant import GRPC_STATUS_ERROR
import ujson

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
        response = serializers.PutVerifierPrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    
    rsa_encryption = RSAEncryption(public_key=key)
    explorer = Explorer(config.Explorer.api, rsa_encryption)
    return explorer

@hub_blueprint.put("/verifier")
@validate(json=serializers.PutVerifierRequest)
async def hub_put_verifier(request: Request, body: serializers.PutVerifierRequest):
    private_key_path = os.path.join(config.Env.session_keys_path, PRIVATE_KEY)
    try:
        async with aiofiles.open(private_key_path, mode='r') as file:
            private_key = await file.read()
    except FileNotFoundError:
        logger.error("[API] - Private key file not found")
        response = serializers.PutVerifierPrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    
    rsa_encryption = RSAEncryption(private_key=private_key)
    
    # Decrypt
    try:
        proof_hash = rsa_encryption.decrypt(body.proof_hash)
        verifiers = ujson.loads(rsa_encryption.decrypt(body.verifiers))
    except Exception as e:
        logger.error(f"[API] - Decryption failed: {e}")
        response = serializers.PutVerifierDecryptionFailedResponse().model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
        
    if not proof_hash or not verifiers:
        logger.error("[API] - Decryption returned empty data")
        response = serializers.PutVerifierDecryptionFailedResponse().model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
    
    explorer = await get_explorer()
    await explorer.update_verifier(proof_hash, verifiers)
    
    response = serializers.PutVerifierSuccessfullyResponse().model_dump()
    return http_response(status=HttpStatus.OK, **response)

