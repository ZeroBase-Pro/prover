from sanic import Blueprint
from utils.constant import SERVER_LOGGER
import os
from pathlib import PurePosixPath
import importlib
import logging
from application import api

blueprints = []

def register_blueprint(bp):
    blueprints.append(bp)
    return bp

hub_blueprint = register_blueprint(Blueprint(name="hub", url_prefix="/hub", version=1, version_prefix="/api/v"))

def autodiscover_api():
    logger = logging.getLogger(SERVER_LOGGER)

    api_dir = os.path.dirname(os.path.abspath(api.__file__))
    for version in os.listdir(api_dir):
        version_dir = os.path.join(api_dir, version)
        version_dir = PurePosixPath(version_dir)
        if os.path.isdir(version_dir.as_posix()) and version_dir.stem.startswith('__') == False:
            for blueprint in os.listdir(version_dir):
                blueprint_dir = os.path.join(version_dir, blueprint)
                blueprint_dir = PurePosixPath(blueprint_dir)
                if os.path.isdir(blueprint_dir.as_posix()) and blueprint_dir.stem.startswith('__') == False:
                    for sub_router in os.listdir(blueprint_dir):
                        sub_router_dir = os.path.join(blueprint_dir, sub_router)
                        sub_router_dir = PurePosixPath(sub_router_dir)
                        if os.path.isdir(sub_router_dir.as_posix()) and sub_router_dir.stem.startswith('__') == False:
                            for file in os.listdir(sub_router_dir):
                                if file == 'api.py':
                                    logger.info(f"[api] - application.api.{version}.{blueprint}.{sub_router}.api is loaded")
                                    importlib.import_module(f"application.api.{version}.{blueprint}.{sub_router}.api")
                                    break
                                else:
                                    continue

def autodiscover_exceptions():
    logger = logging.getLogger(SERVER_LOGGER)

    api_dir = os.path.dirname(os.path.abspath(api.__file__))
    for version in os.listdir(api_dir):
        version_dir = os.path.join(api_dir, version)
        version_dir = PurePosixPath(version_dir)
        if os.path.isdir(version_dir.as_posix()) and version_dir.stem.startswith('__') == False:
            for blueprint in os.listdir(version_dir):
                blueprint_dir = os.path.join(version_dir, blueprint)
                blueprint_dir = PurePosixPath(blueprint_dir)
                if os.path.isdir(blueprint_dir.as_posix()) and blueprint_dir.stem.startswith('__') == False:
                    for sub_router in os.listdir(blueprint_dir):
                        sub_router_dir = os.path.join(blueprint_dir, sub_router)
                        sub_router_dir = PurePosixPath(sub_router_dir)
                        if os.path.isdir(sub_router_dir.as_posix()) and sub_router_dir.stem.startswith('__') == False:
                            for file in os.listdir(sub_router_dir):
                                if file == 'handler.py':
                                    logger.info(f"[exceptions] - application.api.{version}.{blueprint}.{sub_router}.handler is loaded")
                                    importlib.import_module(f"application.api.{version}.{blueprint}.{sub_router}.handler")
                                    break
                                else:
                                    continue

