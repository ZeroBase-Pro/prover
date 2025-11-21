import fastapi

class HTTPException(fastapi.HTTPException):
    def __init__(self, code=-1, msg="System busy", status_code=500):
        super().__init__(detail={
            "code": code,
            "msg": msg,
        }, status_code=status_code)