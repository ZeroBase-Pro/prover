from utils.constant import TASK_DEMO, TASK_LOGGER
import logging
import asyncio


import scheduler
Scheduler = scheduler.Scheduler()
Logger = logging.getLogger(TASK_LOGGER)

@Scheduler.add_task(TASK_DEMO)
async def demo():
    Logger.info("task: do something")
    await asyncio.sleep(10)
    Logger.info("task: done")