import asyncio
import aiohttp
import aiofiles
import logging
from modules.encryptor import RSAEncryption
import config
from utils.constant import CLI_LOGGER
from typing import List
import ujson

logger = logging.getLogger(CLI_LOGGER)

class Hub:
    def __init__(self, hub_api: str, session_key_path: str, config:config.SampleConfig):
        """
        Initialize the Hub instance.

        Args:
            hub_api (str): The base URL for the hub API.
            session_key_path (str): Path to the session key file.
        """
        self.hub_api = hub_api
        self.session_key_path = session_key_path
        self.config = config

    async def send_result(self, project_name: str, proof_hash: str, duration: int, verifiers: List[str]) -> None:
        """
        Send the computation result to the hub API.

        Args:
            project_name (str): Name of the project.
            proof_hash (str): Proof hash of the computation.
            duration (int): Time taken for the computation in seconds.
            verifier (str): Verifier identifier.
        """
        hub_api = f"{self.hub_api}/api/v1/hub/result"

        try:
            async with aiofiles.open(self.session_key_path, mode='r') as file:
                session_key = await file.read()
        except FileNotFoundError:
            logger.error("[API] - Session key file not found.")
            return
        
        encryptor = RSAEncryption(public_key=session_key)
        # Encrypt the data
        encrypted_project_name = encryptor.encrypt(project_name)
        encrypted_proof_hash = encryptor.encrypt(proof_hash)
        encrypted_duration = encryptor.encrypt(str(duration))
        encrypted_verifiers = encryptor.encrypt(ujson.dumps(verifiers))

        body = {
            "project_name": encrypted_project_name,
            "proof_hash": encrypted_proof_hash,
            "duration": encrypted_duration,
            "verifiers": encrypted_verifiers
        }

        async with aiohttp.ClientSession() as session:
            try:
                response = await session.post(hub_api, json=body, proxy=self.config.Env.proxy)
                if response.status == 200:
                    logger.info("[Result] - Successfully sent result to the hub.")
                else:
                    logger.error(f"[Result] - Failed to send result. Status: {response.status}")
                    response_text = await response.text()
                    logger.error(f"[Result] - Response: {response_text}")
            except aiohttp.ClientError as e:
                logger.error(f"[Result] - An error occurred: {e}")
            except Exception as e:
                logger.error(f"[Result] - Unexpected error: {e}")

    async def update_verifier(self, proof_hash: str, verifiers: List[str]) -> None:
        """
        Send the computation result to the hub API.

        Args:
            project_name (str): Name of the project.
            proof_hash (str): Proof hash of the computation.
            duration (int): Time taken for the computation in seconds.
            verifier (str): Verifier identifier.
        """
        hub_api = f"{self.hub_api}/api/v1/hub/verifier"

        try:
            async with aiofiles.open(self.session_key_path, mode='r') as file:
                session_key = await file.read()
        except FileNotFoundError:
            logger.error("[API] - Session key file not found.")
            return
        
        encryptor = RSAEncryption(public_key=session_key)
        # Encrypt the data
        encrypted_proof_hash = encryptor.encrypt(proof_hash)
        encrypted_verifiers = encryptor.encrypt(ujson.dumps(verifiers))

        body = {
            "proof_hash": encrypted_proof_hash,
            "verifiers": encrypted_verifiers
        }

        async with aiohttp.ClientSession() as session:
            try:
                response = await session.put(hub_api, json=body, proxy=self.config.Env.proxy)
                if response.status == 200:
                    logger.info("[update_verifier] - Successfully update verifier to the hub.")
                    return True
                else:
                    logger.error(f"[update_verifier] - Failed to update verifier. Status: {response.status}")
                    response_text = await response.text()
                    logger.error(f"[update_verifier] - Response: {response_text}")
                    return False
            except aiohttp.ClientError as e:
                logger.error(f"[update_verifier] - An error occurred: {e}")
                return False
            except Exception as e:
                logger.error(f"[update_verifier] - Unexpected error: {e}")
                return False

    async def send_heartbeat(self, interval: int = 10) -> None:
        """
        Send heartbeat to the hub API at regular intervals.

        Args:
            interval (int): The time interval (in seconds) between each heartbeat. Defaults to 10 seconds.
        """
        hub_api = f"{self.hub_api}/api/v1/hub/node"
        logger.info(f"[Heartbeat] - Starting heartbeat to {hub_api} every {interval} seconds.")
        try:
            async with aiofiles.open(self.session_key_path, mode='r') as file:
                session_key = await file.read()
        except FileNotFoundError:
            logger.error("[API] - Session key file not found.")
            return
        print("Session Key:", session_key)
        encryptor = RSAEncryption(public_key=session_key)

        grpc_info = encryptor.encrypt(self.config.Hub.Info.grpc)
        http_info = encryptor.encrypt(self.config.Hub.Info.http)
        body = {"grpc_info": grpc_info, "http_info": http_info}

        while True:
            async with aiohttp.ClientSession() as session:
                try:
                    response = await session.post(hub_api, json=body, proxy=self.config.Env.proxy)
                    if response.status == 200:
                        logger.info("[Heartbeat] - Successfully sent heartbeat to the hub.")
                    else:
                        logger.error(f"[Heartbeat] - Failed to send heartbeat. Status: {response.status}")
                        response_text = await response.text()
                        logger.error(f"[Heartbeat] - Response: {response_text}")
                except aiohttp.ClientError as e:
                    logger.error(f"[Heartbeat] - An error occurred: {e}")
                except Exception as e:
                    logger.error(f"[Heartbeat] - Unexpected error: {e}")

                await asyncio.sleep(interval)
