class BaseException(Exception):
    def __init__(self, msg: str = "Null"):
        super().__init__(msg)
        self.msg = msg

    def __str__(self):
        return self.msg

class SystemException(BaseException):
    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg

class ArgsException(BaseException):
    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg

class ContentException(BaseException):
    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg

class RequestException(BaseException):
    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg
