"""AI processing logic for Discord message analysis"""

import asyncio
import logging
from typing import Optional

from app.models import Decision
from app.services.dispatcher import AsyncDispatcher
from model.summary.summary import get_summary_analyzer

logger = logging.getLogger(__name__)

# 출력 시 날짜/기간을 한글로 통일하기 위한 프롬프트 문구 (모든 프롬프트에 공통으로 넣을 수 있음)
_PROMPT_LANG_RULE = (
    "답변은 반드시 한국어로만 작성하고, 날짜·기간·시간은 한글로 표기하세요. "
    "예: 2026년 1월 30일, 다음 주 금요일, 3일 내, 오늘 오후 5시, 이번 주."
)


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
            return await self.analyzer.summarize_async(combined)

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
            time_range = "최근 1시간"
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
            "아래 대화에서 핵심 결정 사항을 추출해 주세요. "
            "각 결정을 (제목, 담당자, 마감일) 형식으로 한 줄씩 나열하세요. "
            f"{_PROMPT_LANG_RULE}\n\n" + combined
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
                        title = line.strip()[:100]
                        decisions.append(
                            Decision(
                                title=title,
                                owner="Unknown",
                                deadline="",
                                context=combined[:200]
                            )
                        )

            if not decisions and messages:
                decisions = [
                    Decision(
                        title="논의 내용 기록",
                        owner="팀",
                        deadline="",
                        context=f"{len(messages)}개 메시지 분석 결과"
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
            f"아래 대화를 바탕으로 간결한 캐치업(지금까지의 흐름 요약)을 작성해 주세요. {_PROMPT_LANG_RULE}\n\n" + combined
        )

        # Create future for result
        future: asyncio.Future[tuple[str, list[str]]] = asyncio.Future()

        async def catchup_task() -> tuple[str, list[str]]:
            """Actual catchup generation task"""
            narrative = await self.analyzer.summarize_async(prompt, max_length=200, min_length=30)

            key_points = []
            prompt_kp = (
                f"아래 대화에서 핵심 포인트 3가지를 목록으로 제시해 주세요. {_PROMPT_LANG_RULE}\n\n" + combined
            )
            kp_text = await self.analyzer.summarize_async(prompt_kp, max_length=150, min_length=20)
            if kp_text:
                key_points = [line.strip() for line in kp_text.split("\n") if line.strip()][:3]

            if not key_points:
                key_points = ["논의 내용 요약"] if messages else []

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
