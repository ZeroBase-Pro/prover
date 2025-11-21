from pydantic import BaseModel, Field
from typing import Union, Optional, List
from utils.response import successfully, args_invalid, rate_limit, request_error, private_key_not_exist, public_key_not_exist, register_failed, decryption_failed

class GrpcInfoModel(BaseModel):
    address: str
    timestamp: int

class HttpInfoModel(BaseModel):
    address: str
    timestamp: int

class NodeInfoModel(BaseModel):
    grpc_info: GrpcInfoModel
    http_info: HttpInfoModel
    poh: str

class PostNodeRequest(BaseModel):
    grpc_info: str
    http_info: str

class GetNodeSuccessfullyResponse(BaseModel):
    code: int = Field(default=successfully.code)
    msg: str = Field(default=successfully.msg)
    results: Optional[List[NodeInfoModel]] = Field(default=None)
    proof_hash: str

class GetNodePublicKeyNotExistResponse(BaseModel):
    code: int = Field(default=public_key_not_exist.code)
    msg: str = Field(default=public_key_not_exist.msg)
    results: Optional[List[NodeInfoModel]] = Field(default=None)

class GetNodePrivateKeyNotExistResponse(BaseModel):
    code: int = Field(default=private_key_not_exist.code)
    msg: str = Field(default=private_key_not_exist.msg)
    results: Optional[List[NodeInfoModel]] = Field(default=None)


class PostNodeSuccessfullyResponse(BaseModel):
    code: int = Field(default=successfully.code)
    msg: str = Field(default=successfully.msg)
    results: Optional[List[NodeInfoModel]] = Field(default=None)

class PostNodeRegisterFailedResponse(BaseModel):
    code: int = Field(default=register_failed.code)
    msg: str = Field(default=register_failed.msg)
    results: Optional[str] = Field(default=None)

class PostNodePrivateKeyNotExistResponse(BaseModel):
    code: int = Field(default=private_key_not_exist.code)
    msg: str = Field(default=private_key_not_exist.msg)
    results: Optional[str] = Field(default=None)

class PostNodeDecryptionFailedResponse(BaseModel):
    code: int = Field(default=decryption_failed.code)
    msg: str = Field(default=decryption_failed.msg)
    results: Optional[str] = Field(default=None)

class RequestErrorResponse(BaseModel):
    code: int = Field(default=request_error.code)
    msg: str = Field(default=request_error.msg)
    results: Optional[Union[dict, list, str]] = Field(default=None)

class ArgsInvalidResponse(BaseModel):
    code: int = Field(default=args_invalid.code)
    msg: str = Field(default=args_invalid.msg)
    results: Optional[Union[dict, list, str]] = Field(default=None)

class RateLimitResponse(BaseModel):
    code: int = Field(default=rate_limit.code)
    msg: str = Field(default=rate_limit.msg)
    results: Optional[Union[dict, list, str]] = Field(default=None)