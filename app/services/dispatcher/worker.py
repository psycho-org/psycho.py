"""Worker module for task processing"""

import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional

logger = logging.getLogger(__name__)


class Worker:
    """Processes tasks from a queue"""

    def __init__(
        self,
        worker_id: int,
        task_queue: asyncio.Queue,
        task_timeout: Optional[float] = None
    ):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.task_timeout = task_timeout
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _execute_task(self, coro: Coroutine) -> Any:
        """Execute task with optional timeout"""
        if self.task_timeout:
            return await asyncio.wait_for(coro, timeout=self.task_timeout)
        return await coro

    async def _execute_callback(self, callback: Callable, result: Any) -> None:
        """Execute callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(result)
            else:
                callback(result)
        except Exception as cb_error:
            logger.error(
                f"Worker {self.worker_id} callback error: {cb_error}",
                exc_info=True
            )

    async def run(self) -> None:
        """Main worker loop"""
        self._running = True
        logger.info(f"Worker {self.worker_id} started")

        while self._running:
            try:
                # Get task from queue with timeout
                task_item = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                if task_item is None:  # Shutdown signal
                    self.task_queue.task_done()
                    break

                coro, callback = task_item
                logger.info(
                    f"Worker {self.worker_id} picked up task. "
                    f"Queue size: {self.task_queue.qsize()}"
                )

                try:
                    result = await self._execute_task(coro)

                    if callback:
                        await self._execute_callback(callback, result)

                    logger.info(f"Worker {self.worker_id} completed task")

                except asyncio.TimeoutError:
                    logger.error(
                        f"Worker {self.worker_id} task timed out after {self.task_timeout}s"
                    )
                except Exception as e:
                    logger.error(f"Worker {self.worker_id} task error: {e}", exc_info=True)

                finally:
                    self.task_queue.task_done()
                    logger.debug(f"Worker {self.worker_id} is idle")

            except asyncio.TimeoutError:
                # No task available, continue loop
                continue
            except Exception as e:
                logger.error(f"Worker {self.worker_id} unexpected error: {e}", exc_info=True)

        logger.info(f"Worker {self.worker_id} stopped")

    def stop(self) -> None:
        """Stop the worker"""
        self._running = False

    def start(self) -> asyncio.Task:
        """Start the worker and return the task"""
        self._task = asyncio.create_task(self.run())
        return self._task
