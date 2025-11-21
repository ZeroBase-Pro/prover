import asyncio
import aiofiles
import aiofiles.os
from typing import Optional, Tuple

from modules.encryptor import RSAEncryption

class KeyCache:
    """
    RSA key caching based on file mtime:
    - Cache after the first read
    - Hot update when private/public key file mtime changes
    """
    def __init__(self, private_key_path: str, public_key_path: str):
        self._private_key_path = private_key_path
        self._public_key_path = public_key_path
        self._lock = asyncio.Lock()
        self._cache: Optional[Tuple[float, float, RSAEncryption]] = None

    async def get_encryptor(self) -> RSAEncryption:
        async with self._lock:
            priv_stat = await aiofiles.os.stat(self._private_key_path)
            pub_stat = await aiofiles.os.stat(self._public_key_path)
            priv_mtime, pub_mtime = priv_stat.st_mtime, pub_stat.st_mtime

            if self._cache and self._cache[0] == priv_mtime and self._cache[1] == pub_mtime:
                return self._cache[2]

            async with aiofiles.open(self._private_key_path, mode="r") as f:
                private_key = await f.read()
            async with aiofiles.open(self._public_key_path, mode="r") as f:
                public_key = await f.read()

            encryptor = RSAEncryption(public_key=public_key, private_key=private_key)
            self._cache = (priv_mtime, pub_mtime, encryptor)
            return encryptor