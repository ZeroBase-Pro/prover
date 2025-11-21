
class Response(object):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

request_error = Response(-1000, "request error")
timeout_error = Response(-1001, "Time out")
args_invalid = Response(-1002, "Arg invalid or isn't specified")
token_error = Response(-1003, "Token expied")
rate_limit = Response(-1004, "Arg invalid or isn't specified")
authorized_error = Response(-1005, "Permission invalid")
private_key_not_exist = Response(-1006, "Private key is not exist")
public_key_not_exist = Response(-1007, "Public key is not exist")
decryption_failed = Response(-1008, "Decryption failed")
register_failed = Response(-1009, "Register failed")

successfully = Response(0, "Successfully")