import hashlib
import time
import logging
from modules.encryptor import RSAEncryption
import threading


class ProofManager:
    _instance = None
    _locker = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(ProofManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, logger:logging.Logger, encryptor:RSAEncryption):
        if self._initialized:
            return
        
        self.logger = logger
        self.encryptor = encryptor

        self._initialized = True

    def set_encryptor(self, encryptor: RSAEncryption):
        self.encryptor = encryptor

    def generate_signature(self, data: str) -> str:
        """
        Generate a digital signature for the given data using the private key.

        :param data: The data to sign.
        :return: The base64-encoded signature.
        """
        self.logger.debug(f"Generating signature for data: {data}")
        signature = self.encryptor.sign(data)
        self.logger.debug(f"Generated signature: {signature}")
        return signature

    def generate_proof_hash(self, data: str) -> str:

        self.logger.debug(f"Generating proof hash")
        timestamp = str(int(time.time()*1000))
        poh_input = f"{data}-{timestamp}"
        proof_hash = f"0x{hashlib.sha256(poh_input.encode()).hexdigest()}"
        
        self.logger.debug(f"Generated proof hash: {proof_hash}")
        return proof_hash
