from config import Config
import asyncio
import sys
import logging
import uvicorn 

from scheduler import Scheduler
from utils.logger import setup_logger
from utils.create_app import create_app
from utils.router import autodiscover_api, autodiscover_exceptions, blueprints
from utils import cli
from utils.constant import API_LOGGER, TASK_LOGGER, JOB_LOGGER, SERVER_LOGGER, SCHEDULER_LOGGER
from middleware.request_handling.request_handling import request_handling


# Initialize configuration and loggers
config = Config()
setup_logger(SERVER_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(SCHEDULER_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(API_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(TASK_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)
setup_logger(JOB_LOGGER, config.Env.logs_path, "MIDNIGHT", logging.DEBUG)

logger = logging.getLogger(SERVER_LOGGER)
app = create_app(
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
    """Start the scheduler after the server starts."""
    scheduler_task = loop.create_task(scheduler.start())
    asyncio.gather(scheduler_task)
    logger.info("Service started")


@app.before_server_stop
async def stop_scheduler(app, loop):
    """Stop the scheduler before the server stops and clean up async generators."""
    await asyncio.sleep(0.1)
    await scheduler.shutdown()
    await asyncio.get_event_loop().shutdown_asyncgens()
    logger.info("Service stopped")

for bp in blueprints:
    logger.info(f"[Blueprint] - [{bp.name}] loaded")
    app.blueprint(bp)


def main():
    logger.info(f"Starting development server at http://{config.Server.Sanic.host}:{config.Server.Sanic.port}")
    uvicorn.run(
        app="src.main:app", 
        host=config.Server.Sanic.host,
        port=config.Server.Sanic.port,
        access_log=False,
        reload=True 
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli.main()
        sys.exit(0)

    main()