from utils.constant import JOB_LOGGER
import logging

from scheduler import Scheduler
from config import Config

from modules.node_list import NodeList

config = Config()
scheduler = Scheduler()
logger = logging.getLogger(JOB_LOGGER)


@scheduler.add_job("update_node_list", 60)
async def update_node_list():
    node_list = NodeList()
    node_list.set_timeout(60)
    node_list.remove_inactive_nodes()
    logger.debug("[Job][UpdateNodeList] - Updated node list, current nodes count: %d", len(node_list.nodes))