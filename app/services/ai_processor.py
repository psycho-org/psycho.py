"""AI processing logic for Discord message analysis"""

import asyncio
import logging
from typing import Optional

from app.models import Decision
from app.services.decision import (
    parse_decisions_from_json,
    parse_decisions_from_lines,
    create_placeholder_decision,
)
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

    def _truncate(self, text: str, max_chars: int = 8000) -> str:
        return text if len(text) <= max_chars else text[:max_chars]

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

        combined = self._truncate("\n".join(messages))

        # Create future for result
        future: asyncio.Future[str] = asyncio.Future()

        async def summarize_task() -> str:
            """Actual summarization task"""
            return await self.analyzer.summarize_async(combined, max_length=220, min_length=60)

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

        combined = self._truncate("\n".join(messages))
        prompt = (
            "아래 대화에서 의사결정을 추출하세요. 모든 텍스트 필드는 반드시 한국어로 작성합니다. "
            "오직 JSON만 출력하세요(마크다운/코드펜스 금지).\n\n"
            f"{_PROMPT_LANG_RULE}\n\n"
            "DECISION CATEGORIES (영문 그대로 사용): schedule, technical, business, policy, resource\n\n"
            "각 결정 항목에 포함: \n"
            "- title: 구체적이고 실행 가능한 제목(한국어, 최대 200자)\n"
            "- owner: 담당자 또는 팀(한국어)\n"
            "- deadline: ISO 날짜(YYYY-MM-DD) 또는 빈 문자열\n"
            "- category: [schedule, technical, business, policy, resource] 중 하나\n"
            "- priority: [low, medium, high, critical] 중 하나\n"
            "- context: 배경/근거/영향(한국어)\n"
            "- notes: 메모(선택, 한국어)\n\n"
            "출력 형식: 의사결정의 JSON 배열만.\n\n"
            "CONVERSATION:\n" + combined
        )

        # Create future for result
        future: asyncio.Future[list[Decision]] = asyncio.Future()

        async def extract_task() -> list[Decision]:
            """Actual decision extraction task"""
            extraction = await self.analyzer.summarize_async(prompt, max_length=350, min_length=50)
            decisions = []

            if extraction:
                # Try to parse JSON response
                decisions = parse_decisions_from_json(extraction, combined)

                # Fallback: parse as lines if JSON parsing yielded no results
                if not decisions:
                    logger.warning("JSON parsing failed. Falling back to line parsing.")
                    decisions = parse_decisions_from_lines(extraction, combined)

            # Fallback if no decisions extracted
            if not decisions and messages:
                decisions = [create_placeholder_decision(len(messages), combined)]

            # Deduplicate decisions
            try:
                from app.services.decision.factory import dedup_decisions as _dedup
                decisions = _dedup(decisions)
            except Exception as e:
                logger.exception("dedup_decisions failed: %s", e)

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

        combined = self._truncate("\n".join(messages))
        prompt = (
            f"아래 대화를 바탕으로 간결한 캐치업(지금까지의 흐름 요약)을 작성해 주세요. {_PROMPT_LANG_RULE}\n\n" + combined
        )

        # Create future for result
        future: asyncio.Future[tuple[str, list[str]]] = asyncio.Future()

        async def catchup_task(combined: str, prompt_narr: str) -> tuple[str, list[str]]:
            import json, re

            # 1) 단일 호출(JSON)
            prompt_json = (
                f"아래 대화를 바탕으로 간결한 캐치업과 핵심 포인트 3가지를 생성하세요. "
                f"{_PROMPT_LANG_RULE}\n"
                "반드시 JSON만 출력:\n"
                "반드시 STRICT JSON 형식으로만 반환할 것.\n"
                "JSON 키는 다음과 같아야 한다:\n"
                "- narrative: 문자열 (요약 서술)\n"
                "- key_points: 짧은 문자열 3개로 이루어진 배열\n"
                "확실하지 않은 경우에도 가능한 최선의 결과를 생성하시오.\n"
                "대화 내용:\n\n" + combined
            )
            resp = await self.analyzer.summarize_async(prompt_json, max_length=260, min_length=60)

            narrative, key_points = "", []

            # 코드펜스/잡음 제거 후 JSON 파싱 시도
            if resp:
                text = resp.strip()
                m = re.search(r"\{.*\}", text, flags=re.S)
                if m:
                    try:
                        obj = json.loads(m.group(0))
                        narrative = str(obj.get("narrative", "")).strip()
                        kp = obj.get("key_points", [])
                        if isinstance(kp, list):
                            key_points = [str(x).strip() for x in kp if str(x).strip()][:3]
                    except Exception as e:
                        logger.warning(f"JSON parse failed: {e}")

            # 2) 내러티브 보강
            if not narrative:
                narrative = await self.analyzer.summarize_async(prompt_narr, max_length=200, min_length=30)

            # 3) 키포인트 보강(필요 시)
            if not key_points:
                prompt_kp = f"아래 대화에서 핵심 포인트 3가지를 목록으로 제시: {_PROMPT_LANG_RULE}\n\n{combined}"
                kp_text = await self.analyzer.summarize_async(prompt_kp, max_length=150, min_length=20)
                if kp_text:
                    key_points = [line.strip() for line in kp_text.splitlines() if line.strip()][:3]
                if not key_points:
                    key_points = ["논의 내용 요약"] if combined.strip() else []

            return narrative, key_points

        def result_callback(result: tuple[str, list[str]]) -> None:
            """Callback when task completes - set future result"""
            if not future.done():
                future.set_result(result)

        # Submit task to dispatcher
        try:
            await self.dispatcher.submit_task(
                catchup_task(combined, prompt),
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
