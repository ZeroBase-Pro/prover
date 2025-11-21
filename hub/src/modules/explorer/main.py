import aiohttp
import logging
from modules.encryptor import RSAEncryption
from config import Config
from utils.constant import CLI_LOGGER
from typing import List
import ujson

config = Config()
logger = logging.getLogger(CLI_LOGGER)

class Explorer:
    def __init__(self, explorer_api: str, encryptor: RSAEncryption):
        self.explorer_api = explorer_api
        self.encryptor = encryptor

    async def send_proof(self, project_name: str, proof_hash: str, duration: int, verifiers: str) -> None:

        explorer_api = f"{self.explorer_api}/api/v1/data/proof"

        body = {
            "project_name": self.encryptor.encrypt(project_name),
            "proof_hash": self.encryptor.encrypt(proof_hash),
            "duration": self.encryptor.encrypt(duration),
            "verifiers": self.encryptor.encrypt(verifiers)
        }

        async with aiohttp.ClientSession() as session:

            try:
                response = await session.post(explorer_api, json=body)
                if response.status == 200:
                    logger.info("[Result] - Successfully sent result to the explorer.")
                else:
                    logger.error(f"[Result] - Failed to send explorer. Status: {response.status}")
                    response_text = await response.text()
                    logger.error(f"[Result] - Response: {response_text}")
            except aiohttp.ClientError as e:
                logger.error(f"[Result] - An error occurred: {e}")
            except Exception as e:
                logger.error(f"[Result] - Unexpected error: {e}")

    async def update_verifier(self, proof_hash: str, verifiers: List[str]) -> None:

        explorer_api = f"{self.explorer_api}/api/v1/data/verifier"

        body = {
            "proof_hash": self.encryptor.encrypt(proof_hash),
            "verifiers": self.encryptor.encrypt(ujson.dumps(verifiers))
        }

        async with aiohttp.ClientSession() as session:

            try:
                response = await session.put(explorer_api, json=body)
                if response.status == 200:
                    logger.info("[Result] - Successfully sent result to the explorer.")
                else:
                    logger.error(f"[Result] - Failed to send explorer. Status: {response.status}")
                    response_text = await response.text()
                    logger.error(f"[Result] - Response: {response_text}")
            except aiohttp.ClientError as e:
                logger.error(f"[Result] - An error occurred: {e}")
            except Exception as e:
                logger.error(f"[Result] - Unexpected error: {e}")