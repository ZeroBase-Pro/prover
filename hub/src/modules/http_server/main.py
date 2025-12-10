import aiohttp
import asyncio
import logging
from typing import Optional
from utils.constant import API_LOGGER  

class HttpServer:
    def __init__(self, address: str, session: Optional[aiohttp.ClientSession] = None, timeout: float = 6.0, logger: Optional[logging.Logger] = None) -> None:  # * 默认超时从 3s 提升到 6s（方案A）
        """
        Initialize the HttpServer with the target address and optional timeout.

        :param address: The URL to send the GET request to.
        :param timeout: The maximum time (in seconds) to wait for a response.
        """
        self.address = address
        self.logger = logger or logging.getLogger(API_LOGGER)  
        self._session = session
        self._timeout = timeout

    @property
    def session(self) -> aiohttp.ClientSession:
        """Prefer an injected shared session if provided; otherwise create one."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout))
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def ping(self) -> bool:
        """
        Asynchronously send a GET request to the server address and check if the response status is 200.

        :return: True if the server responds with status 200, False otherwise.
        """
        url = f"{self.address}/ping"

        try:
            self.logger.info(f"Attempting to ping {url}")
            async with self.session.get(url, ssl=False) as response:
                self.logger.info(f"Received status {response.status} from {url}")
                return response.status == 200
        except asyncio.TimeoutError:
            self.logger.warning(f"Ping to {url} timed out")
            return False
        except aiohttp.ClientError as e:
            self.logger.error(f"Client error occurred while pinging {url}: {e}")
            return False
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred while pinging {url}: {e}")
            return False
    
    async def push_task(self, proof_hash: str, signature: str) -> bool:
        """
        Asynchronously send a POST request to the server address with a proof hash.

        :param proof_hash: The hash to send to the server.
        :return: True if the server responds with status 200, False otherwise.
        """
        url = f"{self.address}/push_task"
        payload = {"proof_hash": proof_hash, "signature": signature}

        try:
            self.logger.info(f"Attempting to push task to {url} with payload: {payload}")
            async with self.session.post(url, json=payload, ssl=False) as response:
                self.logger.info(f"Received status {response.status} from {url}")
                return response.status == 200
        except asyncio.TimeoutError:
            self.logger.warning(f"Push task to {url} timed out, retrying once")  
            try:
                async with self.session.post(url, json=payload, ssl=False) as response: 
                    self.logger.info(f"[Retry] Received status {response.status} from {url}") 
                    return response.status == 200  
            except asyncio.TimeoutError:
                self.logger.warning(f"[Retry] Push task to {url} timed out again")  
                return False 
        except aiohttp.ClientError as e:
            self.logger.error(f"Client error occurred while pushing task to {url}: {e}")
            return False
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred while pushing task to {url}: {e}")
            return False
