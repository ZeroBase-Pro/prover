import asyncio
import signal
import logging
import uvicorn
import contextlib
from fastapi import FastAPI
from typing import Optional, Dict, Any, Callable

from config import Config, SampleConfig
from utils.constant import OAUTH_PROVIDER_GOOGLE, OAUTH_PROVIDER_TELEGRAM, OAUTH_PROVIDER_X509_GOOGLE
from modules.hub import Hub
import grpc
from modules.prove_service.v1 import ProveServiceV1
from modules.prove_service.v2 import ProveServiceV2
from modules.proof_manager import ProofManager
from modules.project_manager import ProjectManager

from modules.oauth_provider import OAuthProvider, OAuthProviderResolver
from modules.oauth_provider import google, telegram, x509_google

from application.grpc_server.v1 import create_grpc_prover_service as v1_grpc_server
from application.http_server.v1 import create_http_prover_service as v1_http_server

from application.grpc_server.v2 import create_grpc_prover_service as v2_grpc_server
from application.http_server.v2 import create_http_prover_service as v2_http_server

class GrpcServerRunner:
    def __init__(self, host: str, port: int, *services: tuple[Callable[[grpc.Server, Any, ProofManager, Hub], None], Any], proof_manager: ProofManager, hub: Hub):
        self.host = host
        self.port = port
        self.services = services
        self.proof_manager = proof_manager
        self.hub = hub
        self.server = grpc.aio.server()

    async def start(self):
        logging.info(f"[gRPC] - Running on {self.host}:{self.port}")

        # Register all services dynamically
        for register_func, service_impl in self.services:
            register_func(self.server, service_impl, self.proof_manager, self.hub)

        self.server.add_insecure_port(f"{self.host}:{self.port}")
        await self.server.start()
        await self.server.wait_for_termination()


class FastApiServerRunner:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server = None

    async def start(self):
        logging.info(f"[FastAPI] - Running on {self.host}:{self.port}")
        app = FastAPI()
        v1_http_server(app)
        v2_http_server(app)
        config = uvicorn.Config(app=app, host=self.host, port=self.port, loop='auto')
        self.server = uvicorn.Server(config)
        await self.server.serve()


class Server:
    def __init__(self,
                 grpc_runner: GrpcServerRunner,
                 http_runner: FastApiServerRunner,
                 hub: Hub):
        self.grpc_runner = grpc_runner
        self.http_runner = http_runner
        self.hub = hub

    async def run(self, interval: int = 30) -> None:
        await asyncio.gather(
            self.grpc_runner.start(),
            self.http_runner.start(),
            self.hub.send_heartbeat(interval),
        )


class ServerBuilder:
    def __init__(self, config: SampleConfig):
        self.config = config
        self.project_manager = ProjectManager(config.Env.project_path)

    async def build(self,
                    hub_api: str,
                    grpc_host: str,
                    grpc_port: int,
                    fastapi_host: Optional[str] = None,
                    fastapi_port: Optional[int] = None) -> Server:

        fastapi_host = fastapi_host or grpc_host
        fastapi_port = fastapi_port or grpc_port + 1

        # Hub
        hub = Hub(hub_api, self.config.Env.session_keys_path, self.config)

        # OAuth providers
        oauth_provider: Dict[str, OAuthProvider] = {
            OAUTH_PROVIDER_GOOGLE: google.Provider(
                self.config.OauthProvider.Google.api,
                self.config.OauthProvider.Google.circom_bigint_n,
                self.config.OauthProvider.Google.circom_bigint_k
            ),
            OAUTH_PROVIDER_X509_GOOGLE: x509_google.Provider(
                self.config.OauthProvider.X509Google.api,
                self.config.OauthProvider.X509Google.circom_bigint_n,
                self.config.OauthProvider.X509Google.circom_bigint_k
            ),
            # OAUTH_PROVIDER_TELEGRAM: telegram.Provider(
            #     self.config.OauthProvider.Telegram.api,
            #     self.config.OauthProvider.Telegram.circom_bigint_n,
            #     self.config.OauthProvider.Telegram.circom_bigint_k
            # ),
        }

        # Update JWKS
        for provider in oauth_provider.values():
            await provider.update_jwks()

        oauth_resolver = OAuthProviderResolver(self.config.Env.oauth_provider_resolver_path)
        proof_manager = ProofManager(self.config.Env.cache_path)
        project_manager = ProjectManager(self.config.Env.project_path)

        grpc_runner = GrpcServerRunner(grpc_host, grpc_port, 
                                    (v1_grpc_server, ProveServiceV1(project_manager, oauth_provider, oauth_resolver, self.config)),
                                    (v2_grpc_server, ProveServiceV2(project_manager, oauth_provider, oauth_resolver, self.config)),
                                    proof_manager=proof_manager, hub=hub)
        http_runner = FastApiServerRunner(fastapi_host, fastapi_port)

        return Server(grpc_runner, http_runner, hub)