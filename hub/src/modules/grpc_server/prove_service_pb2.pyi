from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProveBaseRequest(_message.Message):
    __slots__ = ("prover_id", "circuit_template_id", "input_data", "is_encrypted", "auth_token")
    PROVER_ID_FIELD_NUMBER: _ClassVar[int]
    CIRCUIT_TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    INPUT_DATA_FIELD_NUMBER: _ClassVar[int]
    IS_ENCRYPTED_FIELD_NUMBER: _ClassVar[int]
    AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    prover_id: str
    circuit_template_id: str
    input_data: str
    is_encrypted: bool
    auth_token: str
    def __init__(self, prover_id: _Optional[str] = ..., circuit_template_id: _Optional[str] = ..., input_data: _Optional[str] = ..., is_encrypted: bool = ..., auth_token: _Optional[str] = ...) -> None: ...

class StatusResponse(_message.Message):
    __slots__ = ("code", "msg")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ...) -> None: ...

class ProveRequest(_message.Message):
    __slots__ = ("base_request", "method", "oauth_provider")
    BASE_REQUEST_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    base_request: ProveBaseRequest
    method: int
    oauth_provider: str
    def __init__(self, base_request: _Optional[_Union[ProveBaseRequest, _Mapping]] = ..., method: _Optional[int] = ..., oauth_provider: _Optional[str] = ...) -> None: ...

class ProveWithWitnessRequest(_message.Message):
    __slots__ = ("base_request", "method", "oauth_provider")
    BASE_REQUEST_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    base_request: ProveBaseRequest
    method: int
    oauth_provider: str
    def __init__(self, base_request: _Optional[_Union[ProveBaseRequest, _Mapping]] = ..., method: _Optional[int] = ..., oauth_provider: _Optional[str] = ...) -> None: ...

class ProveNosha256Request(_message.Message):
    __slots__ = ("base_request", "length", "method", "oauth_provider")
    BASE_REQUEST_FIELD_NUMBER: _ClassVar[int]
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    base_request: ProveBaseRequest
    length: int
    method: int
    oauth_provider: str
    def __init__(self, base_request: _Optional[_Union[ProveBaseRequest, _Mapping]] = ..., length: _Optional[int] = ..., method: _Optional[int] = ..., oauth_provider: _Optional[str] = ...) -> None: ...

class ProveNosha256WithWitnessRequest(_message.Message):
    __slots__ = ("base_request", "length", "method", "oauth_provider")
    BASE_REQUEST_FIELD_NUMBER: _ClassVar[int]
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    base_request: ProveBaseRequest
    length: int
    method: int
    oauth_provider: str
    def __init__(self, base_request: _Optional[_Union[ProveBaseRequest, _Mapping]] = ..., length: _Optional[int] = ..., method: _Optional[int] = ..., oauth_provider: _Optional[str] = ...) -> None: ...

class ProveNosha256OffchainRequest(_message.Message):
    __slots__ = ("base_request", "length", "method", "oauth_provider")
    BASE_REQUEST_FIELD_NUMBER: _ClassVar[int]
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    base_request: ProveBaseRequest
    length: int
    method: int
    oauth_provider: str
    def __init__(self, base_request: _Optional[_Union[ProveBaseRequest, _Mapping]] = ..., length: _Optional[int] = ..., method: _Optional[int] = ..., oauth_provider: _Optional[str] = ...) -> None: ...

class GetPublicKeyResponse(_message.Message):
    __slots__ = ("base_response", "public_key")
    BASE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    base_response: StatusResponse
    public_key: str
    def __init__(self, base_response: _Optional[_Union[StatusResponse, _Mapping]] = ..., public_key: _Optional[str] = ...) -> None: ...

class ProveResponse(_message.Message):
    __slots__ = ("base_response", "proof_data")
    BASE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    PROOF_DATA_FIELD_NUMBER: _ClassVar[int]
    base_response: StatusResponse
    proof_data: str
    def __init__(self, base_response: _Optional[_Union[StatusResponse, _Mapping]] = ..., proof_data: _Optional[str] = ...) -> None: ...

class ProveWithWitnessResponse(_message.Message):
    __slots__ = ("base_response", "proof_data", "witness_data")
    BASE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    PROOF_DATA_FIELD_NUMBER: _ClassVar[int]
    WITNESS_DATA_FIELD_NUMBER: _ClassVar[int]
    base_response: StatusResponse
    proof_data: str
    witness_data: str
    def __init__(self, base_response: _Optional[_Union[StatusResponse, _Mapping]] = ..., proof_data: _Optional[str] = ..., witness_data: _Optional[str] = ...) -> None: ...

class ProveNosha256Response(_message.Message):
    __slots__ = ("base_response", "proof_data")
    BASE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    PROOF_DATA_FIELD_NUMBER: _ClassVar[int]
    base_response: StatusResponse
    proof_data: str
    def __init__(self, base_response: _Optional[_Union[StatusResponse, _Mapping]] = ..., proof_data: _Optional[str] = ...) -> None: ...

class ProveNosha256WithWitnessResponse(_message.Message):
    __slots__ = ("base_response", "proof_data", "witness_data")
    BASE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    PROOF_DATA_FIELD_NUMBER: _ClassVar[int]
    WITNESS_DATA_FIELD_NUMBER: _ClassVar[int]
    base_response: StatusResponse
    proof_data: str
    witness_data: str
    def __init__(self, base_response: _Optional[_Union[StatusResponse, _Mapping]] = ..., proof_data: _Optional[str] = ..., witness_data: _Optional[str] = ...) -> None: ...

class ProveNosha256OffchainResponse(_message.Message):
    __slots__ = ("base_response", "proof_data", "witness_data")
    BASE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    PROOF_DATA_FIELD_NUMBER: _ClassVar[int]
    WITNESS_DATA_FIELD_NUMBER: _ClassVar[int]
    base_response: StatusResponse
    proof_data: bytes
    witness_data: str
    def __init__(self, base_response: _Optional[_Union[StatusResponse, _Mapping]] = ..., proof_data: _Optional[bytes] = ..., witness_data: _Optional[str] = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
