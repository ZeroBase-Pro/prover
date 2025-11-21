from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ProveRequest(_message.Message):
    __slots__ = ("input", "temp")
    INPUT_FIELD_NUMBER: _ClassVar[int]
    TEMP_FIELD_NUMBER: _ClassVar[int]
    input: str
    temp: str
    def __init__(self, input: _Optional[str] = ..., temp: _Optional[str] = ...) -> None: ...

class ProveNosha256Request(_message.Message):
    __slots__ = ("input", "temp", "length")
    INPUT_FIELD_NUMBER: _ClassVar[int]
    TEMP_FIELD_NUMBER: _ClassVar[int]
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    input: str
    temp: str
    length: int
    def __init__(self, input: _Optional[str] = ..., temp: _Optional[str] = ..., length: _Optional[int] = ...) -> None: ...

class ProveResponse(_message.Message):
    __slots__ = ("code", "msg", "proof")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    proof: str
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., proof: _Optional[str] = ...) -> None: ...

class ProveWithWitnessResponse(_message.Message):
    __slots__ = ("code", "msg", "witness", "proof")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    WITNESS_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    witness: str
    proof: str
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., witness: _Optional[str] = ..., proof: _Optional[str] = ...) -> None: ...

class ProveNosha256Response(_message.Message):
    __slots__ = ("code", "msg", "proof")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    proof: str
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., proof: _Optional[str] = ...) -> None: ...

class ProveNosha256WithWitnessResponse(_message.Message):
    __slots__ = ("code", "msg", "witness", "proof")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    WITNESS_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    witness: str
    proof: str
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., witness: _Optional[str] = ..., proof: _Optional[str] = ...) -> None: ...

class ProveNosha256OffchainResponse(_message.Message):
    __slots__ = ("code", "msg", "witness", "proof")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    WITNESS_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    witness: str
    proof: bytes
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., witness: _Optional[str] = ..., proof: _Optional[bytes] = ...) -> None: ...

class ProveResponseV2(_message.Message):
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

class GetRunningProveTasksResponse(_message.Message):
    __slots__ = ("code", "msg", "count")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    code: int
    msg: str
    count: int
    def __init__(self, code: _Optional[int] = ..., msg: _Optional[str] = ..., count: _Optional[int] = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
