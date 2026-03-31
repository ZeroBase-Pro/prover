import grpc
import time

from modules.grpc_server import prove_service_pb2
from modules.grpc_server import prove_service_pb2_grpc

from utils.observability import classify_error
from utils.tls import grpc_channel_credentials, grpc_channel_options

class GrpcServer:
    def __init__(self, address, verify_tls: bool = True, tls_certfile: str | None = None) -> None:
        self.address = address
        self.verify_tls = verify_tls
        self.tls_certfile = tls_certfile

    def _channel(self):
        credentials = grpc_channel_credentials(self.tls_certfile)
        options = grpc_channel_options(self.verify_tls, self.tls_certfile)
        return grpc.aio.secure_channel(self.address, credentials, options=options)

    async def ping_details(self):
        started_at = time.perf_counter()
        try:
            async with self._channel() as channel:
                stub = prove_service_pb2_grpc.ProveServiceStub(channel)
                await stub.Ping(prove_service_pb2.Empty())
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": True,
                "duration_ms": duration_ms,
                "error_type": None,
                "error_msg": None,
                "code": "OK",
            }
        except grpc.aio.AioRpcError as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "error_type": classify_error(error),
                "error_msg": error.details(),
                "code": error.code().name,
            }
        except Exception as error:
            duration_ms = (time.perf_counter() - started_at) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "error_type": classify_error(error),
                "error_msg": str(error),
                "code": "UNKNOWN",
            }

    async def ping(self):
        result = await self.ping_details()
        return result["success"]
