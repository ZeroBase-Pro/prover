import logging
from utils.constant import API_LOGGER
from utils.error import RequestException
from sanic import request

logger = logging.getLogger(API_LOGGER)
async def request_handling(request: request.Request):
    
    request_id = request.id
    request.ctx.request_id = request_id
    request.ctx.real_ip = request.remote_addr
    request.ctx.ua = request.headers.get('user-agent')

    request_params = {}

    try:
        request_method = request.method

        if request_method == 'GET':
            request_params = request.args
        else:
            if 'application/json' in request.content_type: #json
                request_params = request.json
            else:
                request_params = {key: request.form.get(key) for key in request.form.keys()}

        logger.info(f"request_id[{request_id}]-client_ip[{request.ctx.real_ip}]-url[{request.url}]-method[{request_method}]-body[{request_params}]")
        

    except Exception as e:
        raise RequestException(e.__str__())