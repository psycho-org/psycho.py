"""Main dispatcher module"""

import asyncio
import logging
import threading
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
        self._workers: list[Worker] = []

        # State (protected by _state_lock)
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._state_lock = threading.Lock()  # Thread-safe lock for all state

    async def start(self) -> None:
        """Start the worker pool"""
        with self._state_lock:
            if self._running:
                logger.warning("Dispatcher already running")
                return

            # Store event loop for thread-safe operations
            self._loop = asyncio.get_running_loop()
            self._running = True

            # Create and start workers
            for i in range(self.max_workers):
                worker = Worker(
                    worker_id=i,
                    task_queue=self.queue._queue,
                    task_timeout=self.task_timeout
                )
                worker.start()
                self._workers.append(worker)

            logger.info(
                f"Dispatcher started with {self.max_workers} workers, "
                f"max queue size: {self.queue.max_size}"
            )

    async def submit_task(
        self,
        coro: Coroutine[Any, Any, Any],
        callback: Optional[Callable[[Any], Any]] = None,
        block: bool = False
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
        with self._state_lock:
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
        with self._state_lock:
            if not self._running or self._loop is None:
                raise RuntimeError("Dispatcher not started. Call start() first.")
            # Safe to capture loop reference within lock
            loop = self._loop

        async def _async_submit():
            """Async wrapper for submit_task"""
            return await self.submit_task(coro, callback, block=True)

        try:
            # Use run_coroutine_threadsafe to execute async operation from sync context
            future = asyncio.run_coroutine_threadsafe(_async_submit(), loop)
            return future.result(timeout=30.0)  # Generous timeout for ThreadPoolExecutor environments
        except Exception as e:
            logger.error(f"Failed to submit task: {e}")
            raise RuntimeError(f"Failed to submit task: {e}") from e

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
        with self._state_lock:
            if not self._running or self._loop is None:
                return

            # Capture workers reference and mark as shutting down
            workers_to_stop = self._workers.copy()
            self._running = False

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
        for worker in workers_to_stop:
            worker.stop()

        # Send shutdown signals
        for _ in workers_to_stop:
            await self.queue._queue.put(None)

        # Wait for workers to finish
        worker_tasks = [w._task for w in workers_to_stop if w._task]
        await asyncio.gather(*worker_tasks, return_exceptions=True)

        with self._state_lock:
            self._workers.clear()
            self._loop = None  # Clear event loop reference

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
    def workers(self) -> list[Worker]:
        """Get a copy of workers list (thread-safe read)"""
        with self._state_lock:
            return self._workers.copy()

    @property
    def is_running(self) -> bool:
        """Check if dispatcher is running"""
        with self._state_lock:
            return self._running

    @property
    def is_queue_full(self) -> bool:
        """Check if queue is at maximum capacity"""
        return self.queue.is_full
