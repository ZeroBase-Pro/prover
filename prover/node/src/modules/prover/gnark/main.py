import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional, Union, Tuple, Callable, Awaitable, Dict, TypeVar

import grpc

from modules.prover import Prover
from modules.prover.gnark import gnark_prove_pb2 as prove_pb2
from modules.prover.gnark import gnark_prove_pb2_grpc as prove_pb2_grpc
from utils.constant import STATUS_CODE_PROVER_NOT_RESPONSE

# =========================
# Result model
# =========================

@dataclass(slots=True)
class PrivateResult:
    code: int
    msg: str
    proof: Optional[Union[str, bytes]] = None
    proof_solidity: Optional[str] = None
    proof_bytes: Optional[bytes] = None
    public_witness: Optional[str] = None
    public_witness_bytes: Optional[bytes] = None


# =========================
# Connection pool
# =========================

class ConnectionPool:
    """
    Simple gRPC channel pool: supports lazy creation and preheating, unified channel options.
    """
    def __init__(
        self,
        address: str,
        max_connections: int = 100,
        initial_size: int = 0,
        *,
        max_send_message_length: int = 64 * 1024 * 1024,
        max_receive_message_length: int = 64 * 1024 * 1024,
        keepalive_time_ms: int = 60_000,
        keepalive_timeout_ms: int = 20_000,
        ping_min_interval_ms: int = 30_000,
        ping_min_interval_no_data_ms: int = 10_000,
    ):
        self.address = address
        self.max_connections = max_connections
        self._pool: asyncio.Queue[Tuple[grpc.aio.Channel, prove_pb2_grpc.ProveServiceStub]] = asyncio.Queue()
        self._created = 0
        self._closed = False
        self._options = [
            ("grpc.max_send_message_length", max_send_message_length),
            ("grpc.max_receive_message_length", max_receive_message_length),
            ("grpc.keepalive_time_ms", keepalive_time_ms),
            ("grpc.keepalive_timeout_ms", keepalive_timeout_ms),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.http2.max_pings_without_data", 2),
            ("grpc.http2.min_time_between_pings_ms", ping_min_interval_ms),
            ("grpc.http2.min_ping_interval_without_data_ms", ping_min_interval_no_data_ms),
        ]

        initial_size = max(0, min(initial_size, max_connections))
        for _ in range(initial_size):
            self._pool.put_nowait(self._new_pair())

    def _new_pair(self) -> Tuple[grpc.aio.Channel, prove_pb2_grpc.ProveServiceStub]:
        ch = grpc.aio.insecure_channel(self.address, options=self._options)
        stub = prove_pb2_grpc.ProveServiceStub(ch)
        self._created += 1
        return ch, stub

    async def acquire(self) -> Tuple[grpc.aio.Channel, prove_pb2_grpc.ProveServiceStub]:
        if self._closed:
            raise RuntimeError("ConnectionPool is closed")
        try:
            return self._pool.get_nowait()
        except asyncio.QueueEmpty:
            if self._created < self.max_connections:
                return self._new_pair()
            return await self._pool.get()

    async def release(self, pair: Tuple[grpc.aio.Channel, prove_pb2_grpc.ProveServiceStub]) -> None:
        if self._closed:
            ch, _ = pair
            await ch.close()
        else:
            await self._pool.put(pair)

    async def close(self) -> None:
        self._closed = True
        closings = []
        while True:
            try:
                ch, _ = self._pool.get_nowait()
                closings.append(ch.close())
            except asyncio.QueueEmpty:
                break
        if closings:
            await asyncio.gather(*closings, return_exceptions=True)


# =========================
# PrivateProver
# =========================

TReq = TypeVar("TReq")
TResp = TypeVar("TResp")

class PrivateProver(Prover):
    """
    - Singleton by address + pool size
    - Unified _rpc(): deadline + exponential backoff retry (for transient errors)
    - Supports async with
    """
    _instances: Dict[str, "PrivateProver"] = {}

    def __new__(cls, address: str, max_connections: int = 100, **kwargs):
        key = f"{address}::{max_connections}"
        inst = cls._instances.get(key)
        if inst is None:
            inst = super().__new__(cls)
            inst._init(address, max_connections, **kwargs)
            cls._instances[key] = inst
        return inst

    def _init(
        self,
        address: str,
        max_connections: int,
        *,
        pool_initial_size: int = 0,
        rpc_timeout_sec: float = 30.0,
        max_retries: int = 2,
        base_backoff_ms: int = 150,
    ) -> None:
        self.address = address
        self.connection_pool = ConnectionPool(address, max_connections, initial_size=pool_initial_size)
        self.rpc_timeout_sec = rpc_timeout_sec
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms

    async def __aenter__(self) -> "PrivateProver":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @asynccontextmanager
    async def _acquire_stub(self):
        pair = await self.connection_pool.acquire()
        try:
            yield pair
        finally:
            await self.connection_pool.release(pair)

    async def _rpc(
        self,
        accessor: Callable[[prove_pb2_grpc.ProveServiceStub], Callable[[TReq], Awaitable[TResp]]],
        request: TReq,
        *,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> TResp:
        timeout = self.rpc_timeout_sec if timeout is None else timeout
        retries = self.max_retries if retries is None else retries

        attempt = 0
        while True:
            attempt += 1
            try:
                async with self._acquire_stub() as (_, stub):
                    call = accessor(stub)
                    return await call(request, timeout=timeout)
            except grpc.aio.AioRpcError as e:
                code = e.code()
                if attempt <= retries and code in (
                    grpc.StatusCode.UNAVAILABLE,
                    grpc.StatusCode.DEADLINE_EXCEEDED,
                    grpc.StatusCode.INTERNAL,
                ):
                    backoff = min((self.base_backoff_ms / 1000.0) * (2 ** (attempt - 1)), 2.0)
                    await asyncio.sleep(backoff)
                    continue
                raise

    # -------- Public APIs --------

    async def prove_tiga_offchain(self, input_data: str, temp: str) -> PrivateResult:
        req = prove_pb2.ProveRequest(input=input_data, temp=temp)
        try:
            resp = await self._rpc(lambda s: s.ProveTigaOffchain, req)
            return PrivateResult(
                code=resp.code, msg=resp.msg, proof=resp.proof,
                proof_solidity=resp.proof_solidity, proof_bytes=resp.proof_bytes,
                public_witness=resp.public_witness, public_witness_bytes=resp.public_witness_bytes
            )
        except grpc.aio.AioRpcError as e:
            return PrivateResult(code=STATUS_CODE_PROVER_NOT_RESPONSE, msg=f"{e.code().name}: {e.details()}")

    async def prove_binance_offchain(self, input_data: str, temp: str) -> PrivateResult:
        req = prove_pb2.ProveRequest(input=input_data, temp=temp)
        try:
            resp = await self._rpc(lambda s: s.ProveBinanceOffchain, req)
            return PrivateResult(
                code=resp.code, msg=resp.msg, proof=resp.proof,
                proof_solidity=resp.proof_solidity, proof_bytes=resp.proof_bytes,
                public_witness=resp.public_witness, public_witness_bytes=resp.public_witness_bytes
            )
        except grpc.aio.AioRpcError as e:
            return PrivateResult(code=STATUS_CODE_PROVER_NOT_RESPONSE, msg=f"{e.code().name}: {e.details()}")

    async def prove_merkle_offchain(self, input_data: str, temp: str) -> PrivateResult:
        req = prove_pb2.ProveRequest(input=input_data, temp=temp)
        try:
            resp = await self._rpc(lambda s: s.ProveMerkleOffchain, req)
            return PrivateResult(
                code=resp.code, msg=resp.msg, proof=resp.proof,
                proof_solidity=resp.proof_solidity, proof_bytes=resp.proof_bytes,
                public_witness=resp.public_witness, public_witness_bytes=resp.public_witness_bytes
            )
        except grpc.aio.AioRpcError as e:
            return PrivateResult(code=STATUS_CODE_PROVER_NOT_RESPONSE, msg=f"{e.code().name}: {e.details()}")

    async def get_running_prove_tasks(self) -> tuple[int, str, Optional[int]]:
        try:
            resp = await self._rpc(lambda s: s.GetRunningProveTasks, prove_pb2.Empty())
            return resp.code, resp.msg, resp.count
        except grpc.aio.AioRpcError as e:
            return STATUS_CODE_PROVER_NOT_RESPONSE, f"{e.code().name}: {e.details()}", None

    async def close(self) -> None:
        await self.connection_pool.close()