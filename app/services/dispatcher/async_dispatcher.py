"""Main dispatcher module"""

import asyncio
import logging
from typing import Callable, Coroutine, Optional, Any

from .task_queue import TaskQueue
from .worker import Worker

logger = logging.getLogger(__name__)


class AsyncDispatcher:
    """
    Dispatcher that manages a pool of worker tasks to process jobs from a queue.
    
    Workers are kept running and pick up tasks from the queue as they become available.
    When a worker completes a task, it automatically becomes idle and picks up the next
    task from the queue.
    """

    def __init__(
        self,
        max_workers: int = 5,
        max_queue_size: int = 1000,
        task_timeout: Optional[float] = None
    ):
        """
        Initialize the dispatcher.
        
        Args:
            max_workers: Maximum number of concurrent worker tasks
            max_queue_size: Maximum number of tasks in queue (prevents memory exhaustion)
            task_timeout: Optional timeout in seconds for each task (prevents stuck workers)
        """
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if task_timeout is not None and task_timeout <= 0:
            raise ValueError("task_timeout must be positive")

        self.max_workers = max_workers
        self.task_timeout = task_timeout

        # Components
        self.queue = TaskQueue(max_size=max_queue_size)
        self.workers: list[Worker] = []

        # State
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the worker pool"""
        async with self._lock:
            if self._running:
                logger.warning("Dispatcher already running")
                return

            self._running = True

            # Create and start workers
            for i in range(self.max_workers):
                worker = Worker(
                    worker_id=i,
                    task_queue=self.queue._queue,
                    task_timeout=self.task_timeout
                )
                worker.start()
                self.workers.append(worker)

            logger.info(
                f"Dispatcher started with {self.max_workers} workers, "
                f"max queue size: {self.queue.max_size}"
            )

    async def submit_task(
        self,
        coro: Coroutine[Any, Any, Any],
        callback: Optional[Callable[[Any], Any]] = None,
        block: bool = True
    ) -> bool:
        """
        Submit a task to the queue.
        
        Args:
            coro: Coroutine to execute
            callback: Optional callback to invoke with the result (can be sync or async)
            block: If True, wait for space in queue. If False, raise QueueFull if full.
        
        Returns:
            True if task was submitted successfully
        
        Raises:
            RuntimeError: If dispatcher is not running
            asyncio.QueueFull: If queue is full and block=False
        """
        if not self._running:
            raise RuntimeError("Dispatcher not started. Call start() first.")

        return await self.queue.put(coro, callback, block)

    def submit_task_sync(
        self,
        coro: Coroutine[Any, Any, Any],
        callback: Optional[Callable[[Any], Any]] = None
    ) -> bool:
        """
        Submit a task to the queue synchronously (non-blocking).
        Useful when calling from sync context.
        
        Args:
            coro: Coroutine to execute
            callback: Optional callback to invoke with the result
        
        Returns:
            True if task was submitted successfully
        
        Raises:
            RuntimeError: If dispatcher is not running
            asyncio.QueueFull: If queue is full
        """
        if not self._running:
            raise RuntimeError("Dispatcher not started. Call start() first.")

        return self.queue.put_nowait(coro, callback)

    async def wait_completion(self) -> None:
        """Wait for all queued tasks to complete"""
        await self.queue.join()
        logger.info("All tasks completed")

    async def shutdown(self, wait: bool = True, timeout: Optional[float] = None) -> None:
        """
        Shutdown the dispatcher.
        
        Args:
            wait: If True, wait for all queued tasks to complete before shutting down
            timeout: Optional timeout for shutdown operation
        """
        async with self._lock:
            if not self._running:
                return

            logger.info("Shutting down dispatcher...")

            if wait:
                if timeout:
                    try:
                        await asyncio.wait_for(self.wait_completion(), timeout=timeout)
                    except asyncio.TimeoutError:
                        logger.warning(f"Shutdown timed out after {timeout}s")
                else:
                    await self.wait_completion()

            # Stop all workers
            for worker in self.workers:
                worker.stop()

            # Send shutdown signals
            for _ in self.workers:
                await self.queue._queue.put(None)

            # Wait for workers to finish
            worker_tasks = [w._task for w in self.workers if w._task]
            await asyncio.gather(*worker_tasks, return_exceptions=True)

            self.workers.clear()
            self._running = False

            logger.info("Dispatcher shutdown complete")

    @property
    def queue_size(self) -> int:
        """Get current queue size"""
        return self.queue.size

    @property
    def max_queue_size(self) -> int:
        """Get maximum queue size"""
        return self.queue.max_size

    @property
    def is_running(self) -> bool:
        """Check if dispatcher is running"""
        return self._running

    @property
    def is_queue_full(self) -> bool:
        """Check if queue is at maximum capacity"""
        return self.queue.is_full
