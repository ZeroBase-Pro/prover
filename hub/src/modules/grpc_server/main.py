import grpc
import time

from modules.grpc_server import prove_service_pb2
from modules.grpc_server import prove_service_pb2_grpc

from utils.constant import GRPC_STATUS_ERROR, GRPC_STATUS_SUCCESSFULLY

class GrpcServer:
    def __init__(self, address) -> None:
        self.address = address

    async def ping(self):
        try:
            async with grpc.aio.insecure_channel(self.address) as channel:
                stub = prove_service_pb2_grpc.ProveServiceStub(channel)
                await stub.Ping(prove_service_pb2.Empty())
            return True
        except grpc.aio.AioRpcError as e:
            return False
