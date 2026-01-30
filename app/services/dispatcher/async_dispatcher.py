"""Main dispatcher module"""

import asyncio
import concurrent.futures
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
        
        This method returns immediately after scheduling the task,
        it does NOT wait for task completion.
        
        Args:
            coro: Coroutine to execute
            callback: Optional callback to invoke with the result
            
        Returns:
            True if task was accepted (submitted or scheduled)
            
        Raises:
            RuntimeError: If dispatcher is not running
            asyncio.QueueFull: If queue is full
        """
        with self._state_lock:
            if not self._running or self._loop is None:
                raise RuntimeError("Dispatcher not started. Call start() first.")
            # Safe to capture loop reference within lock
            loop = self._loop

        async def _async_submit() -> bool:
            """Async wrapper for submit_task with non-blocking submission"""
            return await self.submit_task(coro, callback, block=False)

        def _handle_future_exception(future: concurrent.futures.Future) -> None:
            """Callback to log any exceptions from async task submission"""
            try:
                future.result()
            except asyncio.QueueFull:
                logger.warning("Task submission failed: queue full")
            except Exception as e:
                logger.error(f"Task submission failed: {e}", exc_info=True)

        # Schedule the coroutine without blocking
        future = asyncio.run_coroutine_threadsafe(_async_submit(), loop)

        # Try to get immediate result (check for immediate exceptions like RuntimeError)
        try:
            result = future.result(timeout=0.0)
            logger.debug("Task submitted successfully")
            return result
        except concurrent.futures.TimeoutError:
            # Task submission is still pending - this is expected
            # Attach callback to handle exceptions asynchronously
            future.add_done_callback(_handle_future_exception)
            logger.debug("Task scheduled for submission")
            return True  # Task was accepted and is being processed
        except asyncio.QueueFull as e:
            # Queue is full - propagate immediately
            logger.warning("Cannot submit task: queue is full")
            raise
        except Exception as e:
            # Other errors should be propagated
            logger.error(f"Failed to submit task: {e}", exc_info=True)
            raise RuntimeError(f"Failed to submit task: {e}") from e

    async def wait_completion(self, timeout: Optional[float] = None) -> None:
        """
        Wait for all queued tasks to complete.
        
        Args:
            timeout: Optional timeout in seconds. If provided, raises asyncio.TimeoutError
                    if tasks don't complete within the timeout period.
        
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        if timeout is not None:
            try:
                await asyncio.wait_for(self.queue.join(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Task completion timed out after {timeout}s")
                raise
        else:
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
        else:
            # When wait=False, drain queue to prevent deadlock when enqueuing sentinels
            # If queue is full and workers are stopped, put() will block forever
            logger.debug("Draining queue before shutdown...")
            try:
                while not self.queue.is_empty:
                    try:
                        # Get and cleanup queue item
                        item = self.queue._queue.get_nowait()

                        # Mark task as done (required for queue.join())
                        self.queue.task_done()

                        # Cleanup coroutine/task if present
                        if item is not None:
                            coro, callback = item
                            # Close coroutine to prevent ResourceWarning
                            if hasattr(coro, 'close'):
                                try:
                                    coro.close()
                                except Exception as close_error:
                                    logger.debug(f"Error closing coroutine: {close_error}")
                    except asyncio.QueueEmpty:
                        break
            except Exception as e:
                logger.warning(f"Error draining queue: {e}")

        # Stop all workers
        for worker in workers_to_stop:
            worker.stop()

        # Send shutdown signals (use put_nowait to avoid blocking)
        sentinels_sent = 0
        for _ in workers_to_stop:
            try:
                self.queue._queue.put_nowait(None)
                sentinels_sent += 1
            except asyncio.QueueFull:
                logger.warning(
                    f"Could not enqueue sentinel signal (sent {sentinels_sent}/{len(workers_to_stop)})"
                )
                # Try draining once more and retry
                try:
                    while not self.queue.is_empty:
                        try:
                            item = self.queue._queue.get_nowait()
                            self.queue.task_done()

                            # Cleanup coroutine if present
                            if item is not None:
                                coro, callback = item
                                if hasattr(coro, 'close'):
                                    try:
                                        coro.close()
                                    except Exception as close_error:
                                        logger.debug(f"Error closing coroutine: {close_error}")
                        except asyncio.QueueEmpty:
                            break
                    self.queue._queue.put_nowait(None)
                    sentinels_sent += 1
                except Exception as drain_error:
                    logger.warning(f"Failed to send sentinel after drain: {drain_error}")

        # Wait for workers to finish with timeout to prevent deadlock
        worker_tasks = [w._task for w in workers_to_stop if w._task]
        if worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*worker_tasks, return_exceptions=True),
                    timeout=5.0  # Prevent indefinite wait
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for workers to finish")

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
