"""AI processing logic for Discord message analysis"""

import asyncio
import logging
from typing import Optional

from app.models import Decision
from app.services.decision import parse_decisions_from_json
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
            "Extract key decisions from the conversation using the Decision Template guidelines.\n\n"
            f"{_PROMPT_LANG_RULE}\n\n"
            "DECISION CATEGORIES:\n"
            "1. Schedule: Timeline, dates, deadlines, milestones\n"
            "2. Technical: Technology choices, architecture, implementation approaches\n"
            "3. Business: Strategy, budget, pricing, market decisions\n"
            "4. Policy: Rules, processes, standards, compliance\n"
            "5. Resource: Team assignments, allocations, capacity\n\n"
            "For each decision, extract:\n"
            "- Title: Clear, specific, and actionable (max 200 chars)\n"
            "- Owner: Person or team responsible\n"
            "- Deadline: ISO format date (YYYY-MM-DD)\n"
            "- Category: One of [schedule, technical, business, policy, resource]\n"
            "- Priority: low, medium, high, or critical\n"
            "- Context: Background, rationale, and impact\n\n"
            "Format output as JSON array of decisions.\n\n"
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
            except Exception:
                pass

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
                '{ "narrative": "<string>", "key_points": ["<string>", "<string>", "<string>"] }\n\n'
                f"{combined}"
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

    async def extract_summary_and_decisions(
        self, messages: list[str], timeout: Optional[float] = None
    ) -> tuple[str, str, list[Decision]]:
        """
        Extract both summary and decisions from messages in parallel.

        Args:
            messages: List of formatted messages
            timeout: Task timeout in seconds (applied to both tasks)

        Returns:
            Tuple of (summary, time_range, decisions)

        Raises:
            RuntimeError: Dispatcher not available or not running
            asyncio.TimeoutError: Task timeout
        """
        if not messages:
            return "", "", []

        if not self.dispatcher or not self.dispatcher.is_running:
            raise RuntimeError("Dispatcher is not available or not running")

        # Single-call combined extraction via dispatcher (no parallel fallback)
        try:
            import json

            if not self.dispatcher or not self.dispatcher.is_running:
                raise RuntimeError("Dispatcher is not available or not running")

            combined = self._truncate("\n".join(messages))
            prompt = (
                "From the conversation, produce STRICT JSON with keys: \n"
                "summary (string), time_range (string), decisions (array of objects with fields: "
                "title, owner, deadline, category, priority, context, notes).\n"
                "Constraints: title<=200 chars; category in [schedule, technical, business, policy, resource]; "
                "priority in [low, medium, high, critical]. Conversation follows:\n\n" + combined
            )

            # Run on dispatcher to ensure single worker task
            future: asyncio.Future[str] = asyncio.Future()

            async def combined_task() -> str:
                return await self.analyzer.summarize_async(prompt, max_length=700, min_length=80)

            def set_result(resp: str) -> None:
                if not future.done():
                    future.set_result(resp)

            await self.dispatcher.submit_task(combined_task(), callback=set_result, block=True)

            if timeout:
                resp = await asyncio.wait_for(future, timeout=timeout)
            else:
                resp = await future

            summary_text = ""
            time_range = "past hour"
            decisions: list[Decision] = []

            if resp:
                try:
                    obj_start = resp.find('{')
                    obj_end = resp.rfind('}')
                    if obj_start != -1 and obj_end != -1:
                        obj = json.loads(resp[obj_start:obj_end + 1])
                        summary_text = str(obj.get('summary', '')).strip()
                        time_range = str(obj.get('time_range', 'past hour')).strip() or 'past hour'
                        items = obj.get('decisions', []) or []
                        if isinstance(items, list):
                            from app.services.decision.factory import create_decision_from_dict
                            for it in items:
                                if isinstance(it, dict):
                                    d = create_decision_from_dict(it, context=combined[:300], messages_content=combined)
                                    if d:
                                        decisions.append(d)
                except Exception:
                    pass

            # If summary is empty, perform a single summarize fallback
            if not summary_text and messages:
                try:
                    s_tuple = await self.summarize(messages, timeout)
                    if isinstance(s_tuple, tuple):
                        summary_text, time_range = s_tuple
                    else:
                        summary_text = s_tuple
                        time_range = "past hour"
                except Exception as e:
                    logger.warning(f"Fallback summarization failed: {e}")

            # If no decisions parsed, perform a single fallback extraction (keeps total calls <= 2)
            if not decisions and messages:
                try:
                    logger.warning("Combined JSON had no decisions; performing single fallback extraction")
                    decisions = await self.extract_decisions(messages, timeout)
                except Exception as e:
                    logger.warning(f"Fallback decisions extraction failed: {e}")
                    decisions = []

            # Deduplicate after fallback as well
            try:
                from app.services.decision.factory import dedup_decisions as _dedup
                decisions = _dedup(decisions)
            except Exception:
                pass

            return summary_text, time_range, decisions

        except asyncio.TimeoutError:
            logger.error(f"Combined extraction timeout after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Combined extraction failed: {e}", exc_info=True)
            raise
