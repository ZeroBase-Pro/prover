from utils.router import hub_blueprint
from utils.util import http_response
from utils.constant import API_LOGGER
from utils.constant import HttpStatus
from utils.constant import PRIVATE_KEY, PUBLIC_KEY
from utils.constant import GRPC_STATUS_ERROR
import asyncio
import aiohttp
import time

from sanic.request import Request
from sanic_ext import validate

from . import serializers

import logging
import os

from config import Config

from modules.node_list import NodeList
from modules.grpc_server import GrpcServer
from modules.http_server import HttpServer
from modules.proof_manager import ProofManager
from modules.key_cache import KeyCache

from typing import List, Optional

config = Config()
logger = logging.getLogger(API_LOGGER)

private_key_path = os.path.join(config.Env.session_keys_path, PRIVATE_KEY)
public_key_path  = os.path.join(config.Env.session_keys_path, PUBLIC_KEY)
_key_cache = KeyCache(private_key_path, public_key_path)
_proof_manager: Optional[ProofManager] = None

# --- Shared HTTP session (connection reuse) ---
_http_session: Optional[aiohttp.ClientSession] = None

async def _get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6.0))
    return _http_session

async def _close_http_session():
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None

# Clean up the shared session when the blueprint/server stops
@hub_blueprint.listener("after_server_stop")
async def _bp_after_stop(app, loop):
    await _close_http_session()

@hub_blueprint.get("/node")
async def hub_get_node(request: Request):
    """GET /node: return available nodes and dispatch tasks to them."""
    t_start = time.perf_counter()
    
    try:
        # [1/4] Load encryptor (signing key)
        t_load_key_start = time.perf_counter()
        rsa_encryption = await _key_cache.get_encryptor()
        t_load_key = (time.perf_counter() - t_load_key_start) * 1000
    except FileNotFoundError:
        logger.error("[API][GET /node] - Key file not found")
        response = serializers.GetNodePrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    except Exception as e:
        logger.exception(f"[API][GET /node] - Load keys failed: {e}")
        response = serializers.GetNodePrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)

    global _proof_manager
    if _proof_manager is None:
        _proof_manager = ProofManager(logger=logger, encryptor=rsa_encryption)
    else:
        _proof_manager.encryptor = rsa_encryption

    proof_manager = _proof_manager 
    node_list_instance = NodeList()
    
    node_models: List[serializers.NodeInfoModel] = []
    
    # [2/4] Generate proof hash and signature
    t_sign_start = time.perf_counter()
    proof_hash = proof_manager.generate_proof_hash(request.id)
    signature = proof_manager.generate_signature(proof_hash)
    t_sign = (time.perf_counter() - t_sign_start) * 1000

    async def process_node(grpc_info, http_info, timestamp, poh, proof_hash, signature):
        """Process a single node: dispatch a task to it."""
        grpc_model = serializers.GrpcInfoModel(address=grpc_info, timestamp=timestamp)
        http_model = serializers.HttpInfoModel(address=http_info, timestamp=timestamp)
        
        session = await _get_http_session()
        http_server = HttpServer(address=http_model.address, session=session)

        # Fire-and-forget push: dispatch task asynchronously without blocking
        asyncio.create_task(http_server.push_task(proof_hash, signature))

        logger.debug(f"[API][GET /node] - Dispatched task to node (fire-and-forget): {http_info}")
        return serializers.NodeInfoModel(
            grpc_info=grpc_model, http_info=http_model, poh=poh
        )
    
    # [3/4] Retrieve nodes and dispatch tasks (retry up to 3 times)
    t_node_process_start = time.perf_counter()
    for attempt in range(3):
        raw_nodes = node_list_instance.get_node()
        
        if not raw_nodes:
            logger.warning(f"[API][GET /node] - Attempt {attempt + 1}/3: No nodes available in NodeList")
            await asyncio.sleep(0.1)  # short wait before retry
            continue
        
        logger.debug(f"[API][GET /node] - Attempt {attempt + 1}/3: Found {len(raw_nodes)} nodes, processing...")
        
        tasks = [process_node(grpc_info, http_info, timestamp, poh, proof_hash, signature) 
                 for grpc_info, http_info, timestamp, poh in raw_nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log exceptions per-node but do not fail the whole batch
        for r in results:
            if isinstance(r, Exception):
                logger.exception("[API][GET /node] - process_node raised exception", exc_info=r)

        node_models = [r for r in results if isinstance(r, serializers.NodeInfoModel)]
        

        if len(node_models) != len(raw_nodes):
            logger.warning(f"[API] - {len(node_models)}/{len(raw_nodes)} Not all nodes processed successfully, retrying...")
            continue
        if all((r is not None) and not isinstance(r, Exception) for r in results):
            break
    
    t_node_process = (time.perf_counter() - t_node_process_start) * 1000

    if not node_models:
        logger.error("[API][GET /node] - Failed to process any nodes after all attempts")
        return http_response(status=HttpStatus.INVALID_REQUEST, msg="Failed to process any nodes.")

    t_response_start = time.perf_counter()
    response = serializers.GetNodeSuccessfullyResponse(results=node_models, proof_hash=proof_hash).model_dump()
    t_response = (time.perf_counter() - t_response_start) * 1000

    t_total = (time.perf_counter() - t_start) * 1000

    # Log all timing metrics in one call to avoid extra I/O
    logger.info(
        f"[API][GET /node] - COMPLETED | "
        f"LoadKey: {t_load_key:.2f}ms | "
        f"Sign: {t_sign:.2f}ms | "
        f"ProcessNodes: {t_node_process:.2f}ms | "
        f"Response: {t_response:.2f}ms | "
        f"TOTAL: {t_total:.2f}ms | "
        f"Nodes: {len(node_models)}"
    )
    
    return http_response(status=HttpStatus.OK, **response)



@hub_blueprint.post("/node")
@validate(json=serializers.PostNodeRequest)
async def hub_post_node(request: Request, body: serializers.PostNodeRequest):
    """POST /node: register a node with the hub."""
    t_start = time.perf_counter()
    
    # [1/4] Load the encryptor (used to decrypt node info)
    t_load_key_start = time.perf_counter()
    try:
        rsa_encryption = await _key_cache.get_encryptor()
    except FileNotFoundError:
        logger.error("[API][POST /node] - Private key file not found")
        response = serializers.PostNodePrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    except Exception as e:
        logger.exception(f"[API][POST /node] - Load private key failed: {e}")
        response = serializers.PostNodePrivateKeyNotExistResponse().model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    t_load_key = (time.perf_counter() - t_load_key_start) * 1000
    
    # [2/4] Decrypt node information
    t_decrypt_start = time.perf_counter()
    try:
        grpc_info = rsa_encryption.decrypt(body.grpc_info)
        http_info = rsa_encryption.decrypt(body.http_info)
    except Exception as e:
        logger.error(f"[API][POST /node] - Decryption failed: {e}")
        response = serializers.PostNodeDecryptionFailedResponse().model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
    t_decrypt = (time.perf_counter() - t_decrypt_start) * 1000

    if not grpc_info or not http_info:
        logger.error("[API][POST /node] - Decryption returned empty data")
        response = serializers.PostNodeDecryptionFailedResponse().model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
    
    logger.debug(f"[API][POST /node] - Decrypted - gRPC: {grpc_info}, HTTP: {http_info}")

    # [3/4] Validate node reachability (ping gRPC and HTTP)
    t_ping_start = time.perf_counter()
    grpc_server = GrpcServer(address=grpc_info)
    session = await _get_http_session()
    http_server = HttpServer(address=http_info, session=session)
    
    try:
        logger.debug("[API][POST /node] - Initiating concurrent pings to gRPC and HTTP servers")
        grpc_ping_coro = grpc_server.ping()
        http_ping_coro = http_server.ping()
        grpc_result, http_result = await asyncio.gather(grpc_ping_coro, http_ping_coro)
        logger.debug(f"[API][POST /node] - Ping results - gRPC: {grpc_result}, HTTP: {http_result}")
    except Exception as e:
        logger.exception(f"[API][POST /node] - Error during ping operations: {e}")
        response = serializers.RequestErrorResponse(results=str(e)).model_dump()
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    t_ping = (time.perf_counter() - t_ping_start) * 1000
    
    # Check the results of both pings
    if not grpc_result or not http_result:
        error_messages = []
        if not grpc_result:
            error_messages.append("gRPC server is unreachable.")
        if not http_result:
            error_messages.append("HTTP server is unreachable.")
        combined_error = " ".join(error_messages)
        logger.error(f"[API][POST /node] - Node validation failed: {combined_error}")
        response = serializers.PostNodeRegisterFailedResponse(results=combined_error).model_dump()
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
    
    # [4/4] Register node into NodeList
    t_register_start = time.perf_counter()
    node_list = NodeList()
    node_list.add(grpc_info, http_info)
    t_register = (time.perf_counter() - t_register_start) * 1000
    
    t_total = (time.perf_counter() - t_start) * 1000

    # Log timing metrics in one call to reduce I/O
    logger.info(
        f"[API][POST /node] - COMPLETED | "
        f"LoadKey: {t_load_key:.2f}ms | "
        f"Decrypt: {t_decrypt:.2f}ms | "
        f"Ping: {t_ping:.2f}ms | "
        f"Register: {t_register:.2f}ms | "
        f"TOTAL: {t_total:.2f}ms | "
        f"Node: {grpc_info}"
    )
    
    response = serializers.PostNodeSuccessfullyResponse().model_dump()
    return http_response(status=HttpStatus.OK, **response)


