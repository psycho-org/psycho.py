"""Task queue module"""

import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class TaskQueue:
    """Manages task queue with size limits"""

    def __init__(self, max_size: int = 1000):
        if max_size < 1:
            raise ValueError("max_size must be at least 1")

        self.max_size = max_size
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)

    async def put(
        self,
        coro: Coroutine[Any, Any, Any],
        callback: Optional[Callable[[Any], Any]] = None,
        block: bool = True
    ) -> bool:
        """
        Add a task to the queue.
        
        Args:
            coro: Coroutine to execute
            callback: Optional callback for result
            block: If True, wait for space. If False, raise QueueFull if full.
        
        Returns:
            True if task was added successfully
        
        Raises:
            asyncio.QueueFull: If queue is full and block=False
        """
        task_item = (coro, callback)

        if block:
            await self._queue.put(task_item)
        else:
            try:
                self._queue.put_nowait(task_item)
            except asyncio.QueueFull:
                logger.warning("Queue is full, task rejected")
                raise

        logger.debug(f"Task added. Queue size: {self.size}")
        return True

    def put_nowait(
        self,
        coro: Coroutine[Any, Any, Any],
        callback: Optional[Callable[[Any], Any]] = None
    ) -> bool:
        """
        Add a task to the queue (non-blocking).
        
        Raises:
            asyncio.QueueFull: If queue is full
        """
        task_item = (coro, callback)

        try:
            self._queue.put_nowait(task_item)
            logger.debug(f"Task added. Queue size: {self.size}")
            return True
        except asyncio.QueueFull:
            logger.warning("Queue is full, task rejected")
            raise

    async def get(self) -> Optional[Tuple]:
        """Get a task from the queue"""
        return await self._queue.get()

    def task_done(self) -> None:
        """Mark a task as done"""
        self._queue.task_done()

    async def join(self) -> None:
        """Wait for all tasks to be processed"""
        await self._queue.join()

    @property
    def size(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        """Check if queue is at maximum capacity"""
        return self._queue.qsize() >= self.max_size

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self._queue.empty()
