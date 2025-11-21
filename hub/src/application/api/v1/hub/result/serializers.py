from pydantic import BaseModel, Field
from typing import Union, Optional, List
from utils.response import successfully, args_invalid, rate_limit, request_error, private_key_not_exist, public_key_not_exist, register_failed, decryption_failed

class PostResultRequest(BaseModel):
    project_name: str
    proof_hash: str
    duration: str
    verifiers: str

class PostResultSuccessfullyResponse(BaseModel):
    code: int = Field(default=successfully.code)
    msg: str = Field(default=successfully.msg)

class PostResultPrivateKeyNotExistResponse(BaseModel):
    code: int = Field(default=private_key_not_exist.code)
    msg: str = Field(default=private_key_not_exist.msg)

class PostResultDecryptionFailedResponse(BaseModel):
    code: int = Field(default=decryption_failed.code)
    msg: str = Field(default=decryption_failed.msg)

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