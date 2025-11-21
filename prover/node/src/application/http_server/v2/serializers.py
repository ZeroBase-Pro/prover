from pydantic import BaseModel, field_validator
from typing import Optional
import base64

class PingResponse(BaseModel):
    code: int
    msg: str

class ProveV2Request(BaseModel):
    prover: str
    circuit_template_id: str
    payload: str
    is_encrypted: bool = False
    auth_token: Optional[str]
    task_type: int = 0
    length: int
    oauth_provider: str
    proof_hash: str

class ProveV2Response(BaseModel):
    code: int
    msg: str
    proof: Optional[str] = None
    proof_solidity: Optional[str] = None
    proof_bytes: Optional[bytes] = None
    public_witness: Optional[str] = None
    public_witness_bytes: Optional[bytes] = None
    
    @field_validator('proof_bytes', mode='before')
    @classmethod
    def proof_to_base85(cls, v):
        """
        Convert bytes to Base85 encoded string.
        
        :param v: Input value (bytes or other)
        :return: Base85 encoded string if input is bytes, otherwise original value
        """
        if isinstance(v, bytes):
            # Encode bytes data to Base85 and return as string
            return base64.b85encode(v).decode('utf-8')
        return v  # Return original value if not bytes
    
    @field_validator('public_witness_bytes', mode='before')
    @classmethod
    def witness_to_base85(cls, v):
        """
        Convert bytes to Base85 encoded string.
        
        :param v: Input value (bytes or other)
        :return: Base85 encoded string if input is bytes, otherwise original value
        """
        if isinstance(v, bytes):
            # Encode bytes data to Base85 and return as string
            return base64.b85encode(v).decode('utf-8')
        return v  # Return original value if not bytes