from logging.handlers import TimedRotatingFileHandler
import logging
import os
import time
import re
import sys

from utils.observability import JsonFormatter


class ReTimedRotatingFileHandler(TimedRotatingFileHandler):
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
 
def setup_logger(logName, logsPath, when, level):
    
    loggerObj = logging.getLogger(logName)
    loggerObj.handlers.clear()

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
 
    logger_formatter = JsonFormatter()

    streamHandler = logging.StreamHandler(sys.stdout)
 
    loggerHandler.setFormatter(logger_formatter)
    streamHandler.setFormatter(logger_formatter)
 
    loggerObj.addHandler(loggerHandler)
    loggerObj.addHandler(streamHandler)
 
    loggerObj.setLevel(level)
    
    loggerObj.propagate=False
 
    return loggerObj
