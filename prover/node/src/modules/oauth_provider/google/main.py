import base64
import aiohttp
import threading
import asyncio
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.padding import OAEP
from cryptography.hazmat.backends import default_backend
from typing import List
from pydantic import BaseModel
import ujson

from modules.oauth_provider import OAuthProvider

class JWK(BaseModel):
    kty: str
    kid: str
    alg: str
    use: str
    n: str
    e: str


class JWKS(BaseModel):
    keys: List[JWK]


class Provider(OAuthProvider):
    _instance = None
    _locker = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(Provider, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, provider_api, circom_bitint_n, circom_bitint_k):
        if self._initialized == True:
            return
        
        self.provider_api = provider_api
        self.circom_bigint_n = circom_bitint_n
        self.circom_bigint_k = circom_bitint_k

        self.jwks: JWKS = None

        self._initialized = True

    async def verify(self, input_data: str) -> bool:
        """
        Verify the input data with the latest JWKS, retrying once if initial verification fails.
        
        Args:
            input_data (str): The input data to be verified.
            
        Returns:
            bool: True if verification is successful, False otherwise.
        """
        if await self._verify(input_data):
            return True
        # If initial verification fails, retry after updating JWKS again
        await self.update_jwks()
        return await self._verify(input_data)

    async def _verify(self, input_data:str):
        try:
            input_data = ujson.loads(input_data)
            input_bigint_bytes = input_data['modulus']
        except:
            return False
        
        for key in self.jwks.keys:

            # Convert JWK to RSA public key
            rsa_pub_key = self._jwk_to_rsa_public_key(key)

            # Perform CIRCOM big integer decomposition on modulus N
            provider_bigint_bytes = self._to_circom_bigint_bytes(rsa_pub_key.public_numbers().n)
            if input_bigint_bytes == provider_bigint_bytes:
                return True
        
        return False


    async def update_jwks(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.provider_api) as response:
                response.raise_for_status()  # Ensure HTTP status is successful (2xx)
                data = await response.json()  # Get JSON data
                self.jwks = JWKS(**data)  # Parse to Pydantic model


    def _jwk_to_rsa_public_key(self, jwk: JWK) -> rsa.RSAPublicKey:
        # Decode N and E
        n_bytes = base64.urlsafe_b64decode(jwk.n + "==")  # Fix base64 padding
        e_bytes = base64.urlsafe_b64decode(jwk.e + "==")
        
        # Convert E to integer
        e = int.from_bytes(e_bytes, byteorder='big')

        # Create RSA public key numbers
        n = int.from_bytes(n_bytes, byteorder='big')
        public_numbers = rsa.RSAPublicNumbers(e, n)
        
        # Create RSA public key
        pub_key = public_numbers.public_key(default_backend())
        return pub_key

    # Convert RSA public key to PEM format
    def _rsa_public_key_to_pem(self, pub_key: rsa.RSAPublicKey) -> bytes:
        pem = pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem

    # Convert big integer to CIRCOM BigInt format
    def _to_circom_bigint_bytes(self, num: int) -> List[str]:
        msk = (1 << self.circom_bigint_n) - 1  # 2^CIRCOM_BIGINT_N - 1
        res = []

        for i in range(self.circom_bigint_k):
            shifted = num >> (i * self.circom_bigint_n)
            chunk = shifted & msk
            res.append(str(chunk))

        return res


