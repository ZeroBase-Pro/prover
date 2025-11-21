# logging_setup.py

import os
import sys
import re
import logging
from logging.handlers import TimedRotatingFileHandler


class ReTimedRotatinFileHandler(TimedRotatingFileHandler):
    """ Custom timed rotating file handler with old log cleanup support """
    def getFilesToDelete(self):
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        for fileName in fileNames:
            if self.extMatch.match(fileName):
                result.append(os.path.join(dirName, fileName))
        if len(result) < self.backupCount:
            result = []
        else:
            result.sort()
            result = result[:len(result) - self.backupCount]
        return result


def splitFileName(filename):
    filePath = filename.split('default.log.')
    return ''.join(filePath)


class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.ERROR


def create_timed_handler(filename, when, level, backup=7):
    handler = ReTimedRotatinFileHandler(
        filename=filename, when=when, interval=1, backupCount=backup, encoding='utf-8')
    
    suffix_map = {
        "S": r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(.log)$",
        "M": r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(.log)$",
        "H": r"^\d{4}-\d{2}-\d{2}_\d{2}(.log)$",
        "D": r"^\d{4}-\d{2}-\d{2}(.log)$",
        "MIDNIGHT": r"^\d{4}-\d{2}-\d{2}(.log)$",
        "W": r"^\d{4}-\d{2}-\d{2}(.log)$"
    }

    handler.suffix = "%Y-%m-%d.log"
    handler.extMatch = re.compile(suffix_map[when], re.ASCII)
    handler.namer = splitFileName
    return handler


def setup_logger(log_name, logs_path, when="MIDNIGHT", level=logging.INFO, apply_to_root=True):
    formatter = logging.Formatter(
        "[%(asctime)s] [%(process)d] [%(levelname)s] - %(name)s.%(module)s.%(funcName)s (%(filename)s:%(lineno)d) - %(message)s"
    )

    # Handlers
    info_log_path = os.path.join(logs_path, "default.log")
    info_handler = create_timed_handler(info_log_path, when, level)
    info_handler.setFormatter(formatter)

    error_log_path = os.path.join(logs_path, "error.log")
    error_handler = create_timed_handler(error_log_path, when, level)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(ErrorFilter())

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Create logger
    logger = logging.getLogger(log_name)
    logger.handlers = []  # Clear duplicates
    logger.setLevel(level)
    logger.addHandler(info_handler)
    logger.addHandler(error_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False

    # Apply to root logger (global default)
    if apply_to_root:
        root_logger = logging.getLogger()
        root_logger.handlers = []
        root_logger.setLevel(level)
        root_logger.addHandler(info_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(stream_handler)

    return logger


def patch_framework_loggers(level=logging.INFO):
    """
    Unified handling of common framework loggers (Sanic, Uvicorn, FastAPI, aiohttp)
    """
    for name in [
        "uvicorn", "uvicorn.access", "uvicorn.error",
        "sanic.root", "sanic.error", "sanic.access",
        "aiohttp.access", "aiohttp.server", "aiohttp.web", "aiohttp"
    ]:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = True  # Let root logger handle it