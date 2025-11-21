from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class GenerateProofRequest(_message.Message):
    __slots__ = ("prover", "circuit_template_id", "payload", "length", "is_encrypted", "auth_token", "task_type", "oauth_provider", "proof_hash")
    PROVER_FIELD_NUMBER: _ClassVar[int]
    CIRCUIT_TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    IS_ENCRYPTED_FIELD_NUMBER: _ClassVar[int]
    AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    TASK_TYPE_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    PROOF_HASH_FIELD_NUMBER: _ClassVar[int]
    prover: str
    circuit_template_id: str
    payload: str
    length: int
    is_encrypted: bool
    auth_token: str
    task_type: int
    oauth_provider: str
    proof_hash: str
    def __init__(self, prover: _Optional[str] = ..., circuit_template_id: _Optional[str] = ..., payload: _Optional[str] = ..., length: _Optional[int] = ..., is_encrypted: bool = ..., auth_token: _Optional[str] = ..., task_type: _Optional[int] = ..., oauth_provider: _Optional[str] = ..., proof_hash: _Optional[str] = ...) -> None: ...

class GenerateProofResponse(_message.Message):
    __slots__ = ("code", "msg", "proof", "proof_solidity", "proof_bytes", "public_witness", "public_witness_bytes")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    PROOF_SOLIDITY_FIELD_NUMBER: _ClassVar[int]
    PROOF_BYTES_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_WITNESS_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_WITNESS_BYTES_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    proof: str
    proof_solidity: str
    proof_bytes: bytes
    public_witness: str
    public_witness_bytes: bytes
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., proof: _Optional[str] = ..., proof_solidity: _Optional[str] = ..., proof_bytes: _Optional[bytes] = ..., public_witness: _Optional[str] = ..., public_witness_bytes: _Optional[bytes] = ...) -> None: ...

class GetPublicKeyResponse(_message.Message):
    __slots__ = ("code", "msg", "public_key")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    public_key: str
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., public_key: _Optional[str] = ...) -> None: ...
