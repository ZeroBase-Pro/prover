import logging
from utils.constant import API_LOGGER
from utils.error import RequestException
from utils.observability import log_event, set_request_id
from sanic import request

logger = logging.getLogger(API_LOGGER)
async def request_handling(request: request.Request):
    
    request_id = request.id
    request.ctx.request_id = request_id
    request.ctx.real_ip = request.remote_addr
    request.ctx.ua = request.headers.get('user-agent')
    set_request_id(request_id)

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

        log_event(
            logger,
            logging.INFO,
            service="hub",
            action="request_received",
            result="accepted",
            request_id=str(request_id),
            message="request_received",
            method=request_method,
            path=request.path,
            url=str(request.url),
            client_ip=request.ctx.real_ip,
            user_agent=request.ctx.ua,
            body=request_params,
        )
        

    except Exception as e:
        raise RequestException(e.__str__())
