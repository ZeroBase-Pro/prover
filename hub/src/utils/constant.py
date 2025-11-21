from enum import IntEnum

class NodeStatus(IntEnum):
    PENDING = 0
    WORKING = 1

class HttpStatus(IntEnum):
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    DELETED = 204
    INVALID_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    SERVER_ERROR = 500

TASK_LOGGER = 'Task'
JOB_LOGGER = 'Job'
CLI_LOGGER = 'Cli'
SERVER_LOGGER = 'Server'
API_LOGGER = 'API'
SCHEDULER_LOGGER = 'Scheduler'

TASK_DEMO = "demo"

PUBLIC_KEY = "public_key"
PRIVATE_KEY = "private_key"

GRPC_STATUS_SUCCESSFULLY = 0
GRPC_STATUS_ERROR = -1