from utils.router import hub_blueprint

from sanic.request import Request
from sanic_ext.exceptions import ValidationError

from utils.response import args_invalid
from utils.util import http_response

from utils.constant import HttpStatus

@hub_blueprint.exception(ValidationError)
async def validation_error(request: Request, exception: ValidationError):
    return http_response(args_invalid.code, args_invalid.msg, exception.message, status=HttpStatus.SERVER_ERROR)