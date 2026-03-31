from config import Config
import asyncio
import sys
import logging
import os
import uvicorn

from scheduler import Scheduler
from utils.logger import setup_logger
from utils.create_app import create_app as create_sanic_app
from utils.router import autodiscover_api, autodiscover_exceptions, blueprints
from utils import cli
from utils.constant import API_LOGGER, TASK_LOGGER, JOB_LOGGER, SERVER_LOGGER, SCHEDULER_LOGGER
from middleware.request_handling.request_handling import request_handling

config = Config()

setup_logger(SERVER_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(SCHEDULER_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(API_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(TASK_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(JOB_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)

logger = logging.getLogger(SERVER_LOGGER)

def build_app():
    app = create_sanic_app(
        config.Env.app,
        config.Server.Sanic.host,
        config.Server.Sanic.port,
        config.Server.Sanic.forwarded_secret,
        config.Server.Sanic.real_ip_header,
        config.Server.Sanic.proxies_count,
        config.Server.Sanic.cors_domains,
    )

    scheduler = Scheduler()

    autodiscover_api()
    autodiscover_exceptions()

    app.middleware(request_handling)

    @app.after_server_start
    async def start_scheduler(app, loop):
        scheduler_task = loop.create_task(scheduler.start())
        asyncio.gather(scheduler_task)
        logger.info("Start the service")

    @app.before_server_stop
    async def stop_scheduler(app, loop):
        await asyncio.sleep(0.1)
        await scheduler.shutdown()
        await asyncio.get_event_loop().shutdown_asyncgens()
        logger.info("Stop the service")

    for bp in blueprints:
        logger.info(f"[Blueprint] - [{bp.name}] is loaded")
        app.blueprint(bp)

    return app


def main():
    ssl_certfile = config.Env.tls_certfile
    ssl_keyfile = config.Env.tls_keyfile
    require_tls = config.Env.require_tls
    if bool(ssl_certfile) != bool(ssl_keyfile):
        raise RuntimeError("SSL_CERTFILE and SSL_KEYFILE must be set together")
    if require_tls and not (ssl_certfile and ssl_keyfile):
        raise RuntimeError("TLS is required but SSL_CERTFILE/SSL_KEYFILE are not configured")

    reload_enabled = os.getenv("UVICORN_RELOAD", "true").lower() in {"1", "true", "yes"}
    workers = int(os.getenv("UVICORN_WORKERS", "1" if reload_enabled else "2"))
    if reload_enabled:
        workers = 1

    uvicorn_kwargs = {
        "app": "src.main:build_app",
        "host": config.Server.Sanic.host,
        "port": config.Server.Sanic.port,
        "access_log": False,
        "reload": reload_enabled,
        "workers": workers,
        "factory": True,
    }
    if ssl_certfile and ssl_keyfile:
        uvicorn_kwargs["ssl_certfile"] = ssl_certfile
        uvicorn_kwargs["ssl_keyfile"] = ssl_keyfile

    scheme = "https" if ssl_certfile and ssl_keyfile else "http"
    logger.info(f"Starting server at {scheme}://{config.Server.Sanic.host}:{config.Server.Sanic.port}")
    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli.main()
        sys.exit(0)

    main()
