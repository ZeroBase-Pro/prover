import aiohttp
import asyncio
import logging
import time
from typing import Optional
from utils.constant import API_LOGGER
from utils.observability import classify_error
from utils.tls import aiohttp_ssl_param

class HttpServer:
    def __init__(
        self,
        address: str,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: float = 6.0,
        logger: Optional[logging.Logger] = None,
        verify_tls: bool = True,
        tls_certfile: Optional[str] = None,
    ) -> None:
        self.address = address
        self.logger = logger or logging.getLogger(API_LOGGER)
        self._session = session
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._tls_certfile = tls_certfile

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout))
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _request_ssl(self):
        return aiohttp_ssl_param(self._verify_tls, self._tls_certfile)
    
    async def ping(self) -> bool:
        result = await self.ping_details()
        return result["success"]

    async def ping_details(self) -> dict:
        url = f"{self.address}/ping"
        started_at = time.perf_counter()

        try:
            async with self.session.get(url, ssl=self._request_ssl()) as response:
                duration_ms = (time.perf_counter() - started_at) * 1000
                success = response.status == 200
                return {
                    "success": success,
                    "duration_ms": duration_ms,
                    "status": response.status,
                    "error_type": None if success else "http_status_error",
                    "error_msg": None if success else f"unexpected_http_status:{response.status}",
                }
        except asyncio.TimeoutError as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "status": None,
                "error_type": classify_error(error),
                "error_msg": str(error),
            }
        except aiohttp.ClientError as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "status": None,
                "error_type": classify_error(error),
                "error_msg": str(error),
            }
        except Exception as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "status": None,
                "error_type": classify_error(error),
                "error_msg": str(error),
            }
    
    async def push_task(self, proof_hash: str, signature: str) -> bool:
        result = await self.push_task_details(proof_hash, signature)
        return result["success"]

    async def push_task_details(self, proof_hash: str, signature: str) -> dict:
        url = f"{self.address}/push_task"
        payload = {"proof_hash": proof_hash, "signature": signature}
        started_at = time.perf_counter()

        try:
            async with self.session.post(url, json=payload, ssl=self._request_ssl()) as response:
                duration_ms = (time.perf_counter() - started_at) * 1000
                success = response.status == 200
                return {
                    "success": success,
                    "duration_ms": duration_ms,
                    "status": response.status,
                    "retries": 0,
                    "timeout": False,
                    "error_type": None if success else "http_status_error",
                    "error_msg": None if success else f"unexpected_http_status:{response.status}",
                }
        except asyncio.TimeoutError as error:
            try:
                async with self.session.post(url, json=payload, ssl=self._request_ssl()) as response:
                    duration_ms = (time.perf_counter() - started_at) * 1000
                    success = response.status == 200
                    return {
                        "success": success,
                        "duration_ms": duration_ms,
                        "status": response.status,
                        "retries": 1,
                        "timeout": True,
                        "error_type": None if success else "http_status_error",
                        "error_msg": None if success else f"unexpected_http_status:{response.status}",
                    }
            except asyncio.TimeoutError as retry_error:
                duration_ms = (time.perf_counter() - started_at) * 1000
                return {
                    "success": False,
                    "duration_ms": duration_ms,
                    "status": None,
                    "retries": 1,
                    "timeout": True,
                    "error_type": classify_error(retry_error),
                    "error_msg": str(retry_error or error),
                }
        except aiohttp.ClientError as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "status": None,
                "retries": 0,
                "timeout": False,
                "error_type": classify_error(error),
                "error_msg": str(error),
            }
        except Exception as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "status": None,
                "retries": 0,
                "timeout": False,
                "error_type": classify_error(error),
                "error_msg": str(error),
            }
