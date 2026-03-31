import asyncio
import signal
import logging
import uvicorn
import contextlib
from fastapi import FastAPI
from typing import Optional, Dict, Any, Callable

from config import Config, NodeConfig
from utils.constant import OAUTH_PROVIDER_GOOGLE, OAUTH_PROVIDER_X509_GOOGLE
from modules.hub import Hub
import grpc
from modules.prove_service.v1 import ProveServiceV1
from modules.prove_service.v2 import ProveServiceV2
from modules.proof_manager import ProofManager
from modules.project_manager import ProjectManager

from modules.oauth_provider import OAuthProvider, OAuthProviderResolver
from modules.oauth_provider import google, x509_google

from application.grpc_server.v1 import create_grpc_prover_service as v1_grpc_server
from application.http_server.v1 import create_http_prover_service as v1_http_server

from application.grpc_server.v2 import create_grpc_prover_service as v2_grpc_server
from application.http_server.v2 import create_http_prover_service as v2_http_server
from utils.tls import load_pem_bytes, normalize_path

class GrpcServerRunner:
    def __init__(
        self,
        host: str,
        port: int,
        *services: tuple[Callable[[grpc.Server, Any, ProofManager, Hub], None], Any],
        proof_manager: ProofManager,
        hub: Hub,
        tls_certfile: str = "",
        tls_keyfile: str = "",
        require_tls: bool = False,
    ):
        self.host = host
        self.port = port
        self.services = services
        self.proof_manager = proof_manager
        self.hub = hub
        self.server = grpc.aio.server()
        self.tls_certfile = normalize_path(tls_certfile)
        self.tls_keyfile = normalize_path(tls_keyfile)
        self.require_tls = require_tls
        if bool(self.tls_certfile) != bool(self.tls_keyfile):
            raise RuntimeError("SSL_CERTFILE and SSL_KEYFILE must be set together")
        if self.require_tls and not (self.tls_certfile and self.tls_keyfile):
            raise RuntimeError("TLS is required but SSL_CERTFILE/SSL_KEYFILE are not configured")

    async def start(self):
        scheme = "grpcs" if self.tls_certfile and self.tls_keyfile else "grpc"
        logging.info(f"[gRPC] - Running on {scheme}://{self.host}:{self.port}")

        for register_func, service_impl in self.services:
            register_func(self.server, service_impl, self.proof_manager, self.hub)

        bind_address = f"{self.host}:{self.port}"
        if self.tls_certfile and self.tls_keyfile:
            credentials = grpc.ssl_server_credentials(
                ((load_pem_bytes(self.tls_keyfile), load_pem_bytes(self.tls_certfile)),)
            )
            self.server.add_secure_port(bind_address, credentials)
        else:
            self.server.add_insecure_port(bind_address)
        await self.server.start()
        await self.server.wait_for_termination()


class FastApiServerRunner:
    def __init__(self, host: str, port: int, tls_certfile: str = "", tls_keyfile: str = "", require_tls: bool = False):
        self.host = host
        self.port = port
        self.server = None
        self.tls_certfile = normalize_path(tls_certfile)
        self.tls_keyfile = normalize_path(tls_keyfile)
        self.require_tls = require_tls
        if bool(self.tls_certfile) != bool(self.tls_keyfile):
            raise RuntimeError("SSL_CERTFILE and SSL_KEYFILE must be set together")

    async def start(self):
        if self.require_tls and not (self.tls_certfile and self.tls_keyfile):
            raise RuntimeError("TLS is required but SSL_CERTFILE/SSL_KEYFILE are not configured")
        scheme = "https" if self.tls_certfile and self.tls_keyfile else "http"
        logging.info(f"[FastAPI] - Running on {scheme}://{self.host}:{self.port}")
        app = FastAPI()
        v1_http_server(app)
        v2_http_server(app)
        config_kwargs = {"app": app, "host": self.host, "port": self.port, "loop": "auto"}
        if self.tls_certfile and self.tls_keyfile:
            config_kwargs["ssl_certfile"] = self.tls_certfile
            config_kwargs["ssl_keyfile"] = self.tls_keyfile
        config = uvicorn.Config(**config_kwargs)
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
    def __init__(self, config: NodeConfig):
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

        hub = Hub(hub_api, self.config.Env.session_keys_path, self.config)

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
        }

        for provider in oauth_provider.values():
            await provider.update_jwks()

        oauth_resolver = OAuthProviderResolver(self.config.Env.oauth_provider_resolver_path)
        proof_manager = ProofManager(self.config.Env.cache_path)
        project_manager = ProjectManager(self.config.Env.project_path)

        grpc_runner = GrpcServerRunner(grpc_host, grpc_port, 
                                    (v1_grpc_server, ProveServiceV1(project_manager, oauth_provider, oauth_resolver, self.config)),
                                    (v2_grpc_server, ProveServiceV2(project_manager, oauth_provider, oauth_resolver, self.config)),
                                    proof_manager=proof_manager,
                                    hub=hub,
                                    tls_certfile=self.config.Env.tls_certfile,
                                    tls_keyfile=self.config.Env.tls_keyfile,
                                    require_tls=self.config.Env.require_tls)
        http_runner = FastApiServerRunner(
            fastapi_host,
            fastapi_port,
            tls_certfile=self.config.Env.tls_certfile,
            tls_keyfile=self.config.Env.tls_keyfile,
            require_tls=self.config.Env.require_tls,
        )

        return Server(grpc_runner, http_runner, hub)
