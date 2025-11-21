import asyncio
import traceback
import logging
from functools import wraps
import uuid
import os
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, List, Set, Optional, Awaitable
from scheduler import tasks, jobs
import importlib
import threading
from utils.constant import SCHEDULER_LOGGER
import time

TaskFunction = Callable[..., Awaitable[Any]]
Decorator = Callable[[TaskFunction], TaskFunction]


class Scheduler:
    _instance: Optional['Scheduler'] = None
    _locker: threading.Lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> 'Scheduler':
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(Scheduler, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized == True:
            return
        
        self.logger: logging.Logger = logging.getLogger(SCHEDULER_LOGGER)
        self.jobs: List[asyncio.Task] = []
        self.tasks: Dict[str, TaskFunction] = {}
        self.job_name_set: Set[str] = set()
        self.tasks_store: Dict[str, Dict[str, Any]] = {}
        self.job_configs: Dict[str, Dict[str, Any]] = {}

        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent tasks

        self._job_identifier: str = str(uuid.uuid1())
        self.shutdown_flag: bool = False

        self.asyncio_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._initialized: bool = True

    @property
    def logging(self) -> logging.Logger:
        return self.logger

    async def _init_loop_by_async(self) -> None:
        """
        Initialize the asyncio event loop.
        """
        self.asyncio_loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.asyncio_loop)

    async def start(self) -> None:
        """
        Start the scheduler by initializing the loop, loading tasks and jobs, and starting job execution.
        """
        await self._init_loop_by_async()
        self._load_tasks()
        self._load_jobs()
        self.logger.info("Scheduler is working now...")
        await self._start_jobs_by_async()

    async def _start_jobs_by_async(self) -> None:
        """
        Start all jobs asynchronously.
        """
        self.jobs.append(asyncio.create_task(self.start_task_handler()))
        await asyncio.gather(*self.jobs)

    def _load_tasks(self) -> None:
        """
        Dynamically load all task modules from the tasks directory.
        """
        tasks_dir: str = os.path.dirname(os.path.abspath(tasks.__file__))
        for task_dir in os.listdir(tasks_dir):
            task_dir_path: str = os.path.join(tasks_dir, task_dir)
            task_dir_pure: PurePosixPath = PurePosixPath(task_dir_path)
            if os.path.isdir(task_dir_pure.as_posix()) and not task_dir_pure.stem.startswith('__'):
                self.logger.info(f"[Task] - [{task_dir_pure.stem}] is loaded")
                importlib.import_module(f"scheduler.tasks.{task_dir_pure.stem}.task")

    def _load_jobs(self) -> None:
        """
        Dynamically load all job modules from the jobs directory.
        """
        jobs_dir: str = os.path.dirname(os.path.abspath(jobs.__file__))
        for job_dir in os.listdir(jobs_dir):
            job_dir_path: str = os.path.join(jobs_dir, job_dir)
            job_dir_pure: PurePosixPath = PurePosixPath(job_dir_path)
            if os.path.isdir(job_dir_pure.as_posix()) and not job_dir_pure.stem.startswith('__'):
                self.logger.info(f"[Job] - [{job_dir_pure.stem}] is loaded")
                importlib.import_module(f"scheduler.jobs.{job_dir_pure.stem}.task")

    async def _safe_execute(
        self,
        func: TaskFunction,
        task_name: str,
        task_id: str,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Safely execute a task with logging and exception handling.
        """
        async def task_wrapper() -> None:
            start_time: float = time.time()
            self.logger.info(f"[Task] - [{task_name}] - [{task_id}] - is working")
            try:
                await func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"[Task] - [{task_name}] - [{task_id}] - error: {e}")
                self.logger.debug(traceback.format_exc())
            finally:
                end_time: float = time.time()
                elapsed_time: float = end_time - start_time
                self.logger.info(f"[Task] - [{task_name}] - [{task_id}] - completed in {elapsed_time} seconds")

        self.asyncio_loop.create_task(task_wrapper())

    def add_task(self, task: str) -> Decorator:
        """
        Decorator to register a new task.
        """
        if task in self.tasks:
            raise Exception(f"Task {task} already exists")

        def decorator(func: TaskFunction) -> TaskFunction:
            self.tasks[task] = func
            return func

        return decorator

    async def run_task(self, task: str, **extra: Any) -> None:
        """
        Run a specific task immediately with concurrency control.
        """
        if task not in self.tasks:
            self.logger.error(f"Task '{task}' is not registered.")
            return

        task_id: str = str(uuid.uuid1())
        async with self.semaphore:
            await self._safe_execute(self.tasks[task], task, task_id, **extra)

    async def run_task_by_queue(self, task: str, **extra: Any) -> str:
        """
        Add a task to the queue to be executed later.
        Returns the task ID.
        """
        if task not in self.tasks:
            self.logger.error(f"Task '{task}' is not registered.")
            return ""

        task_id: str = str(uuid.uuid1())
        self.tasks_store[task_id] = {"task_name": task, "task_args": extra, "status": "pending"}
        self.logger.info(f"Task '{task}' has been queued with ID '{task_id}'.")
        return task_id

    async def start_task_handler(self) -> None:
        """
        Continuously monitor and execute pending tasks from the task queue.
        """
        self.logger.info("Task handler started.")
        while not self.shutdown_flag:
            await asyncio.sleep(0.1)  # Check the task queue periodically
            for task_id, task_info in list(self.tasks_store.items()):
                if task_info["status"] == "pending":
                    task_name: str = task_info["task_name"]
                    task_args: Dict[str, Any] = task_info["task_args"]
                    self.tasks_store[task_id]["status"] = "running"
                    await self._safe_execute(self.tasks[task_name], task_name, task_id, **task_args)
                    self.tasks_store[task_id]["status"] = "done"

    def add_job(self, job_name: str, default_interval: float) -> Decorator:
        """
        Decorator to register a new periodic job.
        """
        if job_name in self.job_name_set:
            raise Exception(f"Job [{job_name}] already exists")
        self.job_name_set.add(job_name)

        def decorator(func: TaskFunction) -> TaskFunction:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> None:
                while not self.shutdown_flag:
                    task_id: str = str(uuid.uuid1())
                    job_config: Dict[str, Any] = self.job_configs.get(
                        job_name, {"interval": default_interval, "status": "running"}
                    )
                    interval: float = job_config.get("interval", default_interval)
                    status: str = job_config.get("status", "pending")
                    if status == "pending":
                        self.logger.warning(f"Job [{job_name}] is not running - status: {status}")
                        await asyncio.sleep(interval)
                        continue
                    await self._safe_execute(func, job_name, task_id, *args, **kwargs)
                    await asyncio.sleep(interval)

            job_task: asyncio.Task = self.asyncio_loop.create_task(wrapper())
            self.jobs.append(job_task)
            self.logger.info(f"Job '{job_name}' has been scheduled to run every {default_interval} seconds.")
            return func

        return decorator

    def handle_job_error(self, func: TaskFunction) -> TaskFunction:
        """
        Decorator to handle errors in job functions.
        """
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Optional[Any]:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                e_traceback: str = traceback.format_exc()
                self.logger.info(e_traceback)
                return

        return wrapper

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the scheduler by cancelling all tasks and jobs.
        """
        self.logger.info("Shutdown initiated.")
        self.shutdown_flag = True

        # Cancel all running jobs
        for job in self.jobs:
            self.logger.info(f"Cancelling job '{job.get_name()}'.")
            job.cancel()

        # Wait for all jobs to be cancelled
        await asyncio.gather(*self.jobs, return_exceptions=True)

        # Cancel all other tasks except the current one
        current_task: asyncio.Task = asyncio.current_task()
        if current_task is not None:
            tasks_to_cancel: List[asyncio.Task] = [
                task for task in asyncio.all_tasks() if task is not current_task
            ]
        else:
            tasks_to_cancel = list(asyncio.all_tasks())

        for task in tasks_to_cancel:
            task.cancel()

        # Wait for all tasks to be cancelled
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        self.asyncio_loop.stop()
        self.logger.info("Scheduler shutdown complete.")