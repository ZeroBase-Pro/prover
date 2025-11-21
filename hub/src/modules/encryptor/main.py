import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

class RSAEncryption:
    def __init__(self, public_key="", private_key=""):
        self._private_key = None
        self._public_key = None
        self.public_key_pem = public_key
        self.private_key_pem = private_key

        if self.public_key_pem:
            self.load_public_key(self.public_key_pem)
        if self.private_key:
            self.load_private_key(self.private_key)

    def load_public_key(self, public_key_pem:str):
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        self._public_key = public_key

    def load_private_key(self, private_key_pem:str):
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,  # Provide password here if the private key is encrypted
            backend=default_backend()
        )
        self._private_key = private_key

    def generate_keys(self, key_size=4096):
        # Generate RSA key pair
        self.key_size = key_size
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()

    def serialize_keys(self):
        # Serialize public key to PEM format
        self.private_key_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Serialize private key to PEM format
        self.public_key_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

    def encrypt(self, plaintext:str):
        # Encrypt data using the public key
        ciphertext = self._public_key.encrypt(
            plaintext.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return base64.b85encode(ciphertext).decode('utf-8')

    def decrypt(self, ciphertext:str):
        # Decrypt data using the private key
        try:
            ciphertext = base64.b85decode(ciphertext)
            plaintext = self._private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

        except ValueError as e:
            return False
        return plaintext.decode()
    
    def sign(self, message: str) -> str:
        """
        Sign a message using the private key.

        :param message: The message to sign.
        :return: The base64-encoded signature.
        """
        signature = self._private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b85encode(signature).decode('utf-8')

    def verify(self, message: str, signature: str) -> bool:
        """
        Verify a message signature using the public key.

        :param message: The message to verify.
        :param signature: The base64-encoded signature to verify.
        :return: True if the signature is valid, False otherwise.
        """
        try:
            signature = base64.b85decode(signature)
            self._public_key.verify(
                signature,
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            return False

    def _serialize_public_key(self):
        # Serialize public key to PEM format
        public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return public_pem

    def _serialize_private_key(self):
        # Serialize private key to PEM format
        private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        return private_pem

    @property
    def public_key(self):
        return self.public_key_pem

    @property
    def private_key(self):
        return self.private_key_pem


# Example usage
if __name__ == "__main__":
    rsa_encryption = RSAEncryption()
    original_text = "Test"

    rsa_encryption.generate_keys()
    rsa_encryption.serialize_keys()
    print(rsa_encryption.public_key)
    print(rsa_encryption.private_key)
    
    
    encrypted_text = rsa_encryption.encrypt(original_text)
    print("Encrypted:", encrypted_text)

    decrypted_text = rsa_encryption.decrypt(encrypted_text)
    print("Decrypted:", decrypted_text)

    sign = rsa_encryption.sign("1234")
    print("sign:", sign)

    verify = rsa_encryption.verify("1234", signature=sign)
    print("verify:", verify)
