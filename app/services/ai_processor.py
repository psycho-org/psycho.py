"""AI processing logic for Discord message analysis"""

import asyncio
import logging
from typing import Optional

from app.models import Decision
from app.services.dispatcher import AsyncDispatcher
from model.summary.summary import get_summary_analyzer

logger = logging.getLogger(__name__)


class AIProcessor:
    """Processor for AI-based message analysis using LGAI EXAONE model with dispatcher"""

    def __init__(self, dispatcher: Optional[AsyncDispatcher] = None):
        """
        Initialize AIProcessor with dispatcher and SummaryAnalyzer.
        
        Args:
            dispatcher: AsyncDispatcher instance. If None, will be provided later.
        """
        self.dispatcher = dispatcher
        self.analyzer = get_summary_analyzer()

    async def summarize(self, messages: list[str], timeout: Optional[float] = None) -> tuple[str, str]:
        """
        Summarize messages using LGAI EXAONE AI model via dispatcher.
        
        Args:
            messages: List of formatted messages
            timeout: Task timeout in seconds
            
        Returns:
            Tuple of (summary, time_range)
            
        Raises:
            RuntimeError: Dispatcher not available or not running
            asyncio.TimeoutError: Task timeout
        """
        if not messages:
            return "", ""

        if not self.dispatcher or not self.dispatcher.is_running:
            raise RuntimeError("Dispatcher is not available or not running")

        combined = "\n".join(messages)

        # Create future for result
        future: asyncio.Future[str] = asyncio.Future()

        async def summarize_task() -> str:
            """Actual summarization task"""
            result = await self.analyzer.summarize_async(combined)
            return result

        def result_callback(result: str) -> None:
            """Callback when task completes - set future result"""
            if not future.done():
                future.set_result(result)

        # Submit task to dispatcher
        try:
            await self.dispatcher.submit_task(
                summarize_task(),
                callback=result_callback,
                block=True
            )
        except asyncio.QueueFull:
            logger.error("Task queue is full")
            raise

        # Wait for result from callback
        try:
            if timeout:
                summary = await asyncio.wait_for(future, timeout=timeout)
            else:
                summary = await future
            time_range = "past hour"
            return summary, time_range
        except asyncio.TimeoutError:
            logger.error(f"Summarization task timeout after {timeout}s")
            raise

    async def extract_decisions(self, messages: list[str], timeout: Optional[float] = None) -> list[Decision]:
        """
        Extract decisions from messages using AI model via dispatcher.
        
        Args:
            messages: List of formatted messages
            timeout: Task timeout in seconds
            
        Returns:
            List of Decision objects
            
        Raises:
            RuntimeError: Dispatcher not available or not running
            asyncio.TimeoutError: Task timeout
        """
        if not messages:
            return []

        if not self.dispatcher or not self.dispatcher.is_running:
            raise RuntimeError("Dispatcher is not available or not running")

        combined = "\n".join(messages)
        prompt = (
            "Extract key decisions from the conversation. "
            "List each decision as (title, owner, deadline):\n\n" + combined
        )

        # Create future for result
        future: asyncio.Future[list[Decision]] = asyncio.Future()

        async def extract_task() -> list[Decision]:
            """Actual decision extraction task"""
            extraction = await self.analyzer.summarize_async(prompt, max_length=300, min_length=50)

            decisions = []
            if extraction:
                lines = extraction.split('\n')
                for line in lines:
                    if line.strip() and len(line) > 10:
                        decisions.append(
                            Decision(
                                title=line.strip()[:100],
                                owner="Unknown",
                                deadline="",
                                context=combined[:200]
                            )
                        )

            if not decisions and messages:
                decisions = [
                    Decision(
                        title="Discussion Captured",
                        owner="Team",
                        deadline="",
                        context=f"Analysis of {len(messages)} messages"
                    )
                ]

            return decisions

        def result_callback(result: list[Decision]) -> None:
            """Callback when task completes - set future result"""
            if not future.done():
                future.set_result(result)

        # Submit task to dispatcher
        try:
            await self.dispatcher.submit_task(
                extract_task(),
                callback=result_callback,
                block=True
            )
        except asyncio.QueueFull:
            logger.error("Task queue is full")
            raise

        # Wait for result from callback
        try:
            if timeout:
                decisions = await asyncio.wait_for(future, timeout=timeout)
            else:
                decisions = await future
            return decisions
        except asyncio.TimeoutError:
            logger.error(f"Decision extraction task timeout after {timeout}s")
            raise

    async def generate_catchup(self, messages: list[str], timeout: Optional[float] = None) -> tuple[str, list[str]]:
        """
        Generate catchup narrative from messages using AI model via dispatcher.
        
        Args:
            messages: List of formatted messages
            timeout: Task timeout in seconds
            
        Returns:
            Tuple of (narrative, key_points)
            
        Raises:
            RuntimeError: Dispatcher not available or not running
            asyncio.TimeoutError: Task timeout
        """
        if not messages:
            return "", []

        if not self.dispatcher or not self.dispatcher.is_running:
            raise RuntimeError("Dispatcher is not available or not running")

        combined = "\n".join(messages)
        prompt = (
            "Generate a concise catchup narrative from the conversation:\n\n" + combined
        )

        # Create future for result
        future: asyncio.Future[tuple[str, list[str]]] = asyncio.Future()

        async def catchup_task() -> tuple[str, list[str]]:
            """Actual catchup generation task"""
            narrative = await self.analyzer.summarize_async(prompt, max_length=200, min_length=30)

            key_points = []
            prompt_kp = (
                "List 3 key points from the conversation:\n\n" + combined
            )
            kp_text = await self.analyzer.summarize_async(prompt_kp, max_length=150, min_length=20)
            if kp_text:
                key_points = [line.strip() for line in kp_text.split('\n') if line.strip()][:3]

            if not key_points:
                key_points = ["Discussion captured"] if messages else []

            return narrative, key_points

        def result_callback(result: tuple[str, list[str]]) -> None:
            """Callback when task completes - set future result"""
            if not future.done():
                future.set_result(result)

        # Submit task to dispatcher
        try:
            await self.dispatcher.submit_task(
                catchup_task(),
                callback=result_callback,
                block=True
            )
        except asyncio.QueueFull:
            logger.error("Task queue is full")
            raise

        # Wait for result from callback
        try:
            if timeout:
                narrative, key_points = await asyncio.wait_for(future, timeout=timeout)
            else:
                narrative, key_points = await future
            return narrative, key_points
        except asyncio.TimeoutError:
            logger.error(f"Catchup generation task timeout after {timeout}s")
            raise
