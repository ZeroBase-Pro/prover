from logging.handlers import TimedRotatingFileHandler
import logging
import os
import time
import re
import sys


class ReTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Time-based rotating log handler.
    """
    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.
        More specific than the earlier method, which just used glob.glob().
        """
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        for fileName in fileNames:
            if self.extMatch.match(fileName):
                result.append(os.path.join(dirName, fileName))
        if len(result) < self.backupCount:
            return []
        result.sort()
        return result[: len(result) - self.backupCount]
 
 
def splitFileName(filename):
    filePath = filename.split('default.log.')
    return ''.join(filePath)
 
def setup_logger(logName, logsPath, when, level):
    
    loggerObj = logging.getLogger(logName)

    logFilePath = f"{logsPath}/default.log"

    loggerHandler = ReTimedRotatingFileHandler(filename=logFilePath, when=when, interval=1, backupCount=7, encoding='utf-8')
    loggerHandler.namer = splitFileName

    loggerHandler.suffix = f"{loggerHandler.suffix}.log"

    suffix = {"S": r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(.log)$",
                "M": r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(.log)$",
                "H": r"^\d{4}-\d{2}-\d{2}_\d{2}(.log)$",
                "D": r"^\d{4}-\d{2}-\d{2}(.log)$",
                "MIDNIGHT": r"^\d{4}-\d{2}-\d{2}(.log)$",
                "W": r"^\d{4}-\d{2}-\d{2}(.log)$"}

    loggerHandler.extMatch = re.compile(suffix[when], re.ASCII)
 
    logger_formatter = logging.Formatter(
        "[%(asctime)s] [%(process)d] [%(levelname)s] - %(name)s.%(module)s.%(funcName)s (%(filename)s:%(lineno)d) - %(message)s")

    streamHandler = logging.StreamHandler(sys.stdout)
 
    loggerHandler.setFormatter(logger_formatter)
    streamHandler.setFormatter(logger_formatter)
 
    loggerObj.addHandler(loggerHandler)
    loggerObj.addHandler(streamHandler)
 
    loggerObj.setLevel(level)
    
    loggerObj.propagate=False
 
    return loggerObj
 
 
if __name__ == "__main__":
    setup_logger("test", "backend/src/logs", "M", 2)
    n = 1
    a = logging.getLogger("test")
    while True:
        a.debug(f"this is debug message")
        a.info(f"this is info message")
        a.warning(f"this is warning message")
        a.error(f"this is error message")
        time.sleep(1)
        n += 1