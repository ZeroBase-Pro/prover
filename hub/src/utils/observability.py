import asyncio
import contextvars
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


_REQUEST_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


def set_request_id(request_id: Optional[str]) -> None:
    _REQUEST_ID.set(str(request_id) if request_id is not None else None)


def get_request_id() -> Optional[str]:
    return _REQUEST_ID.get()


def now_iso(timestamp: Optional[float] = None) -> str:
    ts = time.time() if timestamp is None else timestamp
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def classify_error(error: Optional[BaseException] = None, message: Optional[str] = None) -> str:
    message_text = message if message is not None else (str(error) if error is not None else "")
    lowered = message_text.lower()

    try:
        import grpc

        if isinstance(error, grpc.aio.AioRpcError):
            code_name = error.code().name.lower()
            if code_name == "unavailable":
                if "connection refused" in lowered:
                    return "connection_refused"
                return "grpc_unavailable"
            if code_name == "deadline_exceeded":
                return "network_timeout"
    except Exception:
        pass

    try:
        import aiohttp

        if isinstance(error, aiohttp.ClientConnectorError):
            if "connection refused" in lowered:
                return "connection_refused"
            return "grpc_unavailable" if "grpc" in lowered else "unknown_error"
        if isinstance(error, aiohttp.ClientError) and "unclosed connection" in lowered:
            return "aiohttp_unclosed_connection"
    except Exception:
        pass

    if isinstance(error, asyncio.TimeoutError):
        return "network_timeout"
    if "timeout" in lowered or "timed out" in lowered or "deadline exceeded" in lowered:
        return "network_timeout"
    if "connection refused" in lowered:
        return "connection_refused"
    if "invalid task status" in lowered:
        return "invalid_task_status"
    if "flush" in lowered:
        return "flush_error"
    if "unclosed connection" in lowered:
        return "aiohttp_unclosed_connection"
    if "reentrant" in lowered and "logging" in lowered:
        return "logging_reentrant_error"
    if "unavailable" in lowered and "grpc" in lowered:
        return "grpc_unavailable"
    return "unknown_error"


def log_event(
    logger: logging.Logger,
    level: int,
    *,
    service: str,
    action: str,
    result: Optional[str] = None,
    code: Optional[Any] = None,
    error_type: Optional[str] = None,
    error_msg: Optional[str] = None,
    duration_ms: Optional[float] = None,
    request_id: Optional[str] = None,
    proof_hash: Optional[str] = None,
    hub_name: Optional[str] = None,
    node_address: Optional[str] = None,
    grpc_address: Optional[str] = None,
    http_address: Optional[str] = None,
    message: Optional[str] = None,
    **extra: Any,
) -> None:
    payload: Dict[str, Any] = {
        "timestamp": now_iso(),
        "service": service,
        "request_id": request_id or get_request_id(),
        "proof_hash": proof_hash,
        "hub_name": hub_name,
        "node_address": node_address,
        "grpc_address": grpc_address,
        "http_address": http_address,
        "action": action,
        "result": result,
        "code": code,
        "error_type": error_type,
        "error_msg": error_msg,
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
    }
    payload.update(extra)
    logger.log(level, message or action, extra={"structured": payload})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        structured = getattr(record, "structured", None)
        if structured is None:
            payload: Dict[str, Any] = {
                "timestamp": now_iso(record.created),
                "service": record.name.lower(),
                "action": record.funcName,
                "result": None,
                "code": None,
                "error_type": None,
                "error_msg": None,
                "duration_ms": None,
                "message": record.getMessage(),
            }
        else:
            payload = dict(structured)
            payload.setdefault("timestamp", now_iso(record.created))
        payload["level"] = record.levelname
        payload["logger"] = record.name
        if record.exc_info:
            payload["stacktrace"] = self.formatException(record.exc_info)
            payload.setdefault("error_msg", str(record.exc_info[1]))
        return json.dumps({key: value for key, value in payload.items() if value is not None}, ensure_ascii=False)
