import os
import logging

from utils.constant import PUBLIC_KEY, PRIVATE_KEY
from utils.constant import CLI_LOGGER
from modules.encryptor import RSAEncryption

Logging = logging.getLogger(CLI_LOGGER)

class CryptoKey:
    def __init__(self, crypto_keys_path):
        self.public_key_path = os.path.join(crypto_keys_path, PUBLIC_KEY)
        self.private_key_path = os.path.join(crypto_keys_path, PRIVATE_KEY)
        self.encrytor = RSAEncryption()
    
    def generate_keys(self, key_size:int=2048):
        self.encrytor.serialize_keys()
        with open(self.public_key_path, mode='w') as file:
            file.write(self.encrytor.public_key)
            Logging.info(f"Public key is created in [{self.public_key_path}]")
        with open(self.private_key_path, mode='w') as file:
            file.write(self.encrytor.private_key)
            Logging.info(f"Private key is created in [{self.private_key_path}]")