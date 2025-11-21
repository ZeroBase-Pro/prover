from pydantic import BaseModel, field_validator
from typing import Optional
import base64


class PingResponse(BaseModel):
    code: int
    msg: str


class ProveBaseRequest(BaseModel):
    prover_id: str
    circuit_template_id: str
    input_data: str
    is_encrypted: bool
    auth_token: str

class ProveRequest(ProveBaseRequest):
    proof_hash: str
    method: Optional[int]
    oauth_provider: Optional[str]

class ProveWithWitnessRequest(ProveBaseRequest):
    proof_hash: str
    method: Optional[int]
    oauth_provider: Optional[str]

class ProveNosha256Request(ProveBaseRequest):
    proof_hash: str
    length: int
    method: Optional[int]
    oauth_provider: Optional[str]

class ProveNosha256WithWitnessRequest(ProveBaseRequest):
    proof_hash: str
    length: int
    method: Optional[int]
    oauth_provider: Optional[str]

class ProveNosha256OffchainRequest(ProveBaseRequest):
    proof_hash: str
    length: int
    method: Optional[int]
    oauth_provider: Optional[str]

class PushTaskRequest(BaseModel):
    proof_hash: str
    signature: str

class UpdateVerifierRequest(BaseModel):
    proof_hash: str
    verifier: str

class StatusResponse(BaseModel):
    code: int
    msg: str

class GetPublicKeyResponse(StatusResponse):
    public_key: Optional[str]

class ProveResponse(StatusResponse):
    proof_data: Optional[str]

class ProveWithWitnessResponse(StatusResponse):
    proof_data: Optional[str]
    witness_data: Optional[str]
    
class ProveOffchainResponse(StatusResponse):
    proof_data: Optional[bytes]
    witness_data: Optional[str]

    @field_validator('proof_data', mode='before')
    @classmethod
    def proof_to_base64(cls, v):
        """
        Convert bytes to Base64 encoded string.
        
        :param v: Input value (bytes or other)
        :return: Base64 encoded string if input is bytes, otherwise original value
        """
        if isinstance(v, bytes):
            # Encode bytes data to Base64 and return as string
            return base64.b64encode(v).decode('utf-8')
        return v  # Return original value if not bytes

class ProveNosha256Response(StatusResponse):
    proof_data: Optional[str]

class ProveNosha256WithWitnessResponse(StatusResponse):
    proof_data: Optional[str]
    witness_data: Optional[str]

class ProveNosha256OffchainResponse(StatusResponse):
    proof_data: Optional[bytes]
    witness_data: Optional[str]

    @field_validator('proof_data', mode='before')
    @classmethod
    def proof_to_base64(cls, v):
        """
        Convert bytes to Base64 encoded string.
        
        :param v: Input value (bytes or other)
        :return: Base64 encoded string if input is bytes, otherwise original value
        """
        if isinstance(v, bytes):
            # Encode bytes data to Base64 and return as string
            return base64.b64encode(v).decode('utf-8')
        return v  # Return original value if not bytes