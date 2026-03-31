import asyncio
import aiohttp
import hmac
import ipaddress
import logging
import os
import time
from typing import List, Optional
from urllib.parse import urlparse

from sanic.request import Request
from sanic_ext import validate

from config import Config
from modules.grpc_server import GrpcServer
from modules.http_server import HttpServer
from modules.key_cache import KeyCache
from modules.node_list import NodeList
from modules.proof_manager import ProofManager
from utils.constant import API_LOGGER, HttpStatus, PRIVATE_KEY, PUBLIC_KEY
from utils.observability import classify_error, log_event
from utils.response import authorized_error, request_error, successfully
from utils.router import hub_blueprint
from utils.util import http_response

from . import serializers


config = Config()
logger = logging.getLogger(API_LOGGER)

private_key_path = os.path.join(config.Env.session_keys_path, PRIVATE_KEY)
public_key_path = os.path.join(config.Env.session_keys_path, PUBLIC_KEY)
_key_cache = KeyCache(private_key_path, public_key_path)
_proof_manager: Optional[ProofManager] = None
_NODE_REGISTER_TOKEN_HEADER = "x-node-token"


def _load_allowed_node_cidrs():
    networks = []
    for cidr in getattr(config.Security, "allowed_node_cidrs", []):
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid allowed node CIDR: %s", cidr)
    return tuple(networks)


_ALLOWED_NODE_CIDRS = _load_allowed_node_cidrs()
_ALLOWED_NODE_HOSTS = tuple(getattr(config.Security, "allowed_node_hosts", []))
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


def _request_id(request: Request) -> str:
    return str(getattr(request.ctx, "request_id", request.id))


def _extract_node_register_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.headers.get(_NODE_REGISTER_TOKEN_HEADER, "").strip()


def _hostname_allowed(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    for allowed_host in _ALLOWED_NODE_HOSTS:
        candidate = allowed_host.strip().lower().rstrip(".")
        if not candidate:
            continue
        if candidate.startswith("*."):
            suffix = candidate[1:]
            if normalized.endswith(suffix):
                return True
        elif candidate.startswith("."):
            if normalized.endswith(candidate):
                return True
        elif normalized == candidate:
            return True
    return False


def _host_allowed(host: str) -> bool:
    normalized = host.strip().lower().rstrip(".")
    if not normalized:
        return False

    try:
        ip_obj = ipaddress.ip_address(normalized)
    except ValueError:
        return _hostname_allowed(normalized)

    for network in _ALLOWED_NODE_CIDRS:
        if ip_obj in network:
            return True

    return not any(
        [
            ip_obj.is_private,
            ip_obj.is_loopback,
            ip_obj.is_link_local,
            ip_obj.is_multicast,
            ip_obj.is_reserved,
            ip_obj.is_unspecified,
        ]
    )


def _split_host_port(value: str):
    target = value.strip()
    if target.startswith("["):
        end = target.find("]")
        if end == -1 or end + 1 >= len(target) or target[end + 1] != ":":
            raise ValueError("address must use [host]:port for IPv6")
        return target[1:end], target[end + 2 :]

    host, separator, port_text = target.rpartition(":")
    if not separator or not host:
        raise ValueError("address must be host:port")
    return host, port_text


def _validate_grpc_address(address: str) -> Optional[str]:
    try:
        host, port_text = _split_host_port(address)
        port = int(port_text)
    except ValueError as error:
        return f"invalid grpc_info: {error}"

    if port < 1 or port > 65535:
        return "invalid grpc_info: port out of range"
    if not _host_allowed(host):
        return "invalid grpc_info: host is not allowlisted"
    return None


def _validate_http_address(address: str) -> Optional[str]:
    try:
        parsed = urlparse(address.strip())
    except ValueError as error:
        return f"invalid http_info: {error}"

    if parsed.scheme not in {"http", "https"}:
        return "invalid http_info: scheme must be http or https"
    if not parsed.hostname:
        return "invalid http_info: hostname is required"
    if parsed.username or parsed.password:
        return "invalid http_info: userinfo is not allowed"
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return "invalid http_info: path/query/fragment is not allowed"
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        return f"invalid http_info: {error}"
    if port < 1 or port > 65535:
        return "invalid http_info: port out of range"
    if not _host_allowed(parsed.hostname):
        return "invalid http_info: host is not allowlisted"
    return None


async def _dispatch_task_to_node(
    *,
    request_id: str,
    proof_hash: str,
    signature: str,
    grpc_info: str,
    http_info: str,
    http_server: HttpServer,
) -> None:
    log_event(
        logger,
        logging.INFO,
        service="hub",
        action="push_task_start",
        result="started",
        request_id=request_id,
        proof_hash=proof_hash,
        node_address=grpc_info,
        grpc_address=grpc_info,
        http_address=http_info,
    )
    push_result = await http_server.push_task_details(proof_hash, signature=signature)
    log_event(
        logger,
        logging.INFO if push_result["success"] else logging.ERROR,
        service="hub",
        action="push_task_complete",
        result="success" if push_result["success"] else "failure",
        code=push_result.get("status"),
        error_type=push_result.get("error_type"),
        error_msg=push_result.get("error_msg"),
        duration_ms=push_result["duration_ms"],
        request_id=request_id,
        proof_hash=proof_hash,
        node_address=grpc_info,
        grpc_address=grpc_info,
        http_address=http_info,
    )


@hub_blueprint.listener("after_server_stop")
async def _bp_after_stop(app, loop):
    await _close_http_session()


@hub_blueprint.get("/node")
async def hub_get_node(request: Request):
    t_start = time.perf_counter()
    request_id = _request_id(request)
    log_event(
        logger,
        logging.INFO,
        service="hub",
        action="prove_request_received",
        result="started",
        request_id=request_id,
    )

    try:
        t_load_key_start = time.perf_counter()
        rsa_encryption = await _key_cache.get_encryptor()
        t_load_key = (time.perf_counter() - t_load_key_start) * 1000
    except FileNotFoundError:
        response = serializers.GetNodePrivateKeyNotExistResponse().model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="prove_request_load_key",
            result="failure",
            request_id=request_id,
            error_type="unknown_error",
            error_msg="Key file not found",
        )
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    except Exception as error:
        response = serializers.GetNodePrivateKeyNotExistResponse().model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="prove_request_load_key",
            result="failure",
            request_id=request_id,
            error_type=classify_error(error),
            error_msg=str(error),
        )
        return http_response(status=HttpStatus.SERVER_ERROR, **response)

    global _proof_manager
    if _proof_manager is None:
        _proof_manager = ProofManager(logger=logger, encryptor=rsa_encryption)
    else:
        _proof_manager.encryptor = rsa_encryption

    proof_manager = _proof_manager
    node_list_instance = NodeList()
    node_models: List[serializers.NodeInfoModel] = []

    t_sign_start = time.perf_counter()
    proof_hash = proof_manager.generate_proof_hash(request.id)
    signature = proof_manager.generate_signature(proof_hash)
    t_sign = (time.perf_counter() - t_sign_start) * 1000
    log_event(
        logger,
        logging.INFO,
        service="hub",
        action="prove_hash_assigned",
        result="success",
        request_id=request_id,
        proof_hash=proof_hash,
        duration_ms=t_sign,
    )

    async def process_node(grpc_info, http_info, timestamp, poh, proof_hash, signature):
        grpc_model = serializers.GrpcInfoModel(address=grpc_info, timestamp=timestamp)
        http_model = serializers.HttpInfoModel(address=http_info, timestamp=timestamp)

        session = await _get_http_session()
        http_server = HttpServer(
            address=http_model.address,
            session=session,
            verify_tls=config.Security.verify_node_tls,
            tls_certfile=config.Security.tls_certfile,
        )
        asyncio.create_task(
            _dispatch_task_to_node(
                request_id=request_id,
                proof_hash=proof_hash,
                signature=signature,
                grpc_info=grpc_info,
                http_info=http_info,
                http_server=http_server,
            )
        )
        log_event(
            logger,
            logging.INFO,
            service="hub",
            action="prove_dispatch_enqueued",
            result="queued",
            request_id=request_id,
            proof_hash=proof_hash,
            node_address=grpc_info,
            grpc_address=grpc_info,
            http_address=http_info,
        )
        return serializers.NodeInfoModel(grpc_info=grpc_model, http_info=http_model, poh=poh)

    t_node_process_start = time.perf_counter()
    for attempt in range(3):
        raw_nodes = node_list_instance.get_node()

        if not raw_nodes:
            log_event(
                logger,
                logging.WARNING,
                service="hub",
                action="prove_dispatch_select_node",
                result="empty",
                request_id=request_id,
                proof_hash=proof_hash,
                error_type="unknown_error",
                error_msg="no_nodes_available",
                retry_attempt=attempt + 1,
            )
            await asyncio.sleep(0.1)
            continue

        tasks = [
            process_node(grpc_info, http_info, timestamp, poh, proof_hash, signature)
            for grpc_info, http_info, timestamp, poh in raw_nodes
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in results:
            if isinstance(item, Exception):
                log_event(
                    logger,
                    logging.ERROR,
                    service="hub",
                    action="prove_dispatch_process_node",
                    result="failure",
                    request_id=request_id,
                    proof_hash=proof_hash,
                    error_type=classify_error(item),
                    error_msg=str(item),
                )

        node_models = [item for item in results if isinstance(item, serializers.NodeInfoModel)]

        if len(node_models) != len(raw_nodes):
            log_event(
                logger,
                logging.WARNING,
                service="hub",
                action="prove_dispatch_partial_retry",
                result="retry",
                request_id=request_id,
                proof_hash=proof_hash,
                retry_attempt=attempt + 1,
                selected_nodes=len(raw_nodes),
                dispatched_nodes=len(node_models),
            )
            continue
        if all((item is not None) and not isinstance(item, Exception) for item in results):
            break

    t_node_process = (time.perf_counter() - t_node_process_start) * 1000

    if not node_models:
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="prove_dispatch_complete",
            result="failure",
            request_id=request_id,
            proof_hash=proof_hash,
            code=HttpStatus.INVALID_REQUEST,
            error_type="unknown_error",
            error_msg="failed_to_process_any_nodes",
            duration_ms=(time.perf_counter() - t_start) * 1000,
        )
        return http_response(status=HttpStatus.INVALID_REQUEST, msg="Failed to process any nodes.")

    t_response_start = time.perf_counter()
    response = serializers.GetNodeSuccessfullyResponse(results=node_models, proof_hash=proof_hash).model_dump()
    t_response = (time.perf_counter() - t_response_start) * 1000
    t_total = (time.perf_counter() - t_start) * 1000

    log_event(
        logger,
        logging.INFO,
        service="hub",
        action="prove_dispatch_complete",
        result="success",
        request_id=request_id,
        proof_hash=proof_hash,
        code=successfully.code,
        duration_ms=t_total,
        load_key_ms=round(t_load_key, 3),
        sign_ms=round(t_sign, 3),
        process_nodes_ms=round(t_node_process, 3),
        response_ms=round(t_response, 3),
        selected_nodes=len(node_models),
    )

    time.sleep(0.02)
    return http_response(status=HttpStatus.OK, **response)


@hub_blueprint.post("/node")
@validate(json=serializers.PostNodeRequest)
async def hub_post_node(request: Request, body: serializers.PostNodeRequest):
    t_start = time.perf_counter()
    request_id = _request_id(request)
    log_event(
        logger,
        logging.INFO,
        service="hub",
        action="node_register_start",
        result="started",
        request_id=request_id,
    )

    expected_token = getattr(config.Security, "node_register_token", "").strip()
    if not expected_token:
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_auth",
            result="failure",
            request_id=request_id,
            error_type="configuration_error",
            error_msg="node_register_token_not_configured",
        )
        return http_response(
            code=request_error.code,
            msg="Node registration is disabled",
            result="node_register_token_not_configured",
            status=HttpStatus.SERVER_ERROR,
        )

    actual_token = _extract_node_register_token(request)
    if not actual_token or not hmac.compare_digest(actual_token, expected_token):
        log_event(
            logger,
            logging.WARNING,
            service="hub",
            action="node_register_auth",
            result="failure",
            request_id=request_id,
            error_type="unauthorized",
            error_msg="invalid_node_register_token",
        )
        return http_response(
            code=authorized_error.code,
            msg=authorized_error.msg,
            result="invalid_node_register_token",
            status=HttpStatus.UNAUTHORIZED,
        )

    t_load_key_start = time.perf_counter()
    try:
        rsa_encryption = await _key_cache.get_encryptor()
    except FileNotFoundError:
        response = serializers.PostNodePrivateKeyNotExistResponse().model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_load_key",
            result="failure",
            request_id=request_id,
            error_type="unknown_error",
            error_msg="private_key_not_found",
        )
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    except Exception as error:
        response = serializers.PostNodePrivateKeyNotExistResponse().model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_load_key",
            result="failure",
            request_id=request_id,
            error_type=classify_error(error),
            error_msg=str(error),
        )
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    t_load_key = (time.perf_counter() - t_load_key_start) * 1000

    t_decrypt_start = time.perf_counter()
    try:
        grpc_info = rsa_encryption.decrypt(body.grpc_info)
        http_info = rsa_encryption.decrypt(body.http_info)
    except Exception as error:
        response = serializers.PostNodeDecryptionFailedResponse().model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_decrypt",
            result="failure",
            request_id=request_id,
            error_type=classify_error(error),
            error_msg=str(error),
        )
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)
    t_decrypt = (time.perf_counter() - t_decrypt_start) * 1000

    if not grpc_info or not http_info:
        response = serializers.PostNodeDecryptionFailedResponse().model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_decrypt",
            result="failure",
            request_id=request_id,
            error_type="unknown_error",
            error_msg="decryption_returned_empty_data",
        )
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)

    grpc_validation_error = _validate_grpc_address(grpc_info)
    if grpc_validation_error:
        response = serializers.ArgsInvalidResponse(results=grpc_validation_error).model_dump()
        log_event(
            logger,
            logging.WARNING,
            service="hub",
            action="node_register_validate_address",
            result="failure",
            request_id=request_id,
            error_type="invalid_node_address",
            error_msg=grpc_validation_error,
        )
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)

    http_validation_error = _validate_http_address(http_info)
    if http_validation_error:
        response = serializers.ArgsInvalidResponse(results=http_validation_error).model_dump()
        log_event(
            logger,
            logging.WARNING,
            service="hub",
            action="node_register_validate_address",
            result="failure",
            request_id=request_id,
            error_type="invalid_node_address",
            error_msg=http_validation_error,
        )
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)

    t_ping_start = time.perf_counter()
    grpc_server = GrpcServer(
        address=grpc_info,
        verify_tls=config.Security.verify_node_tls,
        tls_certfile=config.Security.tls_certfile,
    )
    session = await _get_http_session()
    http_server = HttpServer(
        address=http_info,
        session=session,
        verify_tls=config.Security.verify_node_tls,
        tls_certfile=config.Security.tls_certfile,
    )

    try:
        grpc_result, http_result = await asyncio.gather(
            grpc_server.ping_details(),
            http_server.ping_details(),
        )
    except Exception as error:
        response = serializers.RequestErrorResponse(results=str(error)).model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_ping",
            result="failure",
            request_id=request_id,
            grpc_address=grpc_info,
            http_address=http_info,
            node_address=grpc_info,
            error_type=classify_error(error),
            error_msg=str(error),
        )
        return http_response(status=HttpStatus.SERVER_ERROR, **response)
    t_ping = (time.perf_counter() - t_ping_start) * 1000

    log_event(
        logger,
        logging.INFO if grpc_result["success"] else logging.ERROR,
        service="hub",
        action="grpc_ping_result",
        result="success" if grpc_result["success"] else "failure",
        request_id=request_id,
        grpc_address=grpc_info,
        http_address=http_info,
        node_address=grpc_info,
        code=grpc_result.get("code"),
        error_type=grpc_result.get("error_type"),
        error_msg=grpc_result.get("error_msg"),
        duration_ms=grpc_result["duration_ms"],
    )
    log_event(
        logger,
        logging.INFO if http_result["success"] else logging.ERROR,
        service="hub",
        action="http_ping_result",
        result="success" if http_result["success"] else "failure",
        request_id=request_id,
        grpc_address=grpc_info,
        http_address=http_info,
        node_address=grpc_info,
        code=http_result.get("status"),
        error_type=http_result.get("error_type"),
        error_msg=http_result.get("error_msg"),
        duration_ms=http_result["duration_ms"],
    )

    if not grpc_result["success"] or not http_result["success"]:
        error_messages = []
        if not grpc_result["success"]:
            error_messages.append("gRPC server is unreachable.")
        if not http_result["success"]:
            error_messages.append("HTTP server is unreachable.")
        combined_error = " ".join(error_messages)
        response = serializers.PostNodeRegisterFailedResponse(results=combined_error).model_dump()
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_register_validation",
            result="failure",
            request_id=request_id,
            grpc_address=grpc_info,
            http_address=http_info,
            node_address=grpc_info,
            error_type=grpc_result.get("error_type") or http_result.get("error_type"),
            error_msg=combined_error,
            duration_ms=t_ping,
        )
        return http_response(status=HttpStatus.INVALID_REQUEST, **response)

    t_register_start = time.perf_counter()
    node_list = NodeList()
    node_list.add(grpc_info, http_info)
    t_register = (time.perf_counter() - t_register_start) * 1000
    t_total = (time.perf_counter() - t_start) * 1000

    log_event(
        logger,
        logging.INFO,
        service="hub",
        action="node_register_complete",
        result="success",
        request_id=request_id,
        grpc_address=grpc_info,
        http_address=http_info,
        node_address=grpc_info,
        code=successfully.code,
        duration_ms=t_total,
        load_key_ms=round(t_load_key, 3),
        decrypt_ms=round(t_decrypt, 3),
        ping_ms=round(t_ping, 3),
        register_ms=round(t_register, 3),
        node_count=len(node_list.nodes),
    )

    response = serializers.PostNodeSuccessfullyResponse().model_dump()
    return http_response(status=HttpStatus.OK, **response)


def _node_status_payload() -> dict:
    node_list = NodeList()
    nodes_out = []
    for idx, (node_id, node) in enumerate(node_list.nodes.items()):
        nodes_out.append(
            {
                "index": idx,
                "id": node_id,
                "grpc_info": node.get("grpc_info"),
                "http_info": node.get("http_info"),
                "timestamp": node.get("timestamp"),
                "poh": node.get("poh"),
            }
        )
    return {
        "code": successfully.code,
        "msg": successfully.msg,
        "results": {"count": len(nodes_out), "nodes": nodes_out},
    }


@hub_blueprint.get("/node/status")
async def hub_get_node_status(request: Request):
    try:
        response = _node_status_payload()
        return http_response(status=HttpStatus.OK, **response)
    except Exception as error:
        log_event(
            logger,
            logging.ERROR,
            service="hub",
            action="node_status_fetch",
            result="failure",
            request_id=_request_id(request),
            error_type=classify_error(error),
            error_msg=str(error),
        )
        return http_response(status=HttpStatus.SERVER_ERROR, msg="Internal Server Error")
