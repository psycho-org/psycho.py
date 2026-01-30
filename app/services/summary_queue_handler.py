"""
Summary Queue Handler - 큐를 통한 요약 작업 처리 및 결과 반환
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.services.dispatcher import AsyncDispatcher
from model.summary.summary_service import SummaryService

logger = logging.getLogger(__name__)


class SummaryQueueHandler:
    """큐를 통해 요약 작업을 처리하고 결과를 반환하는 핸들러"""

    def __init__(
        self,
        dispatcher: AsyncDispatcher,
        summary_service: Optional[SummaryService] = None
    ):
        """
        Args:
            dispatcher: 작업을 처리할 AsyncDispatcher 인스턴스
            summary_service: SummaryService 인스턴스 (None이면 새로 생성)
        """
        self.dispatcher = dispatcher
        self.summary_service = summary_service or SummaryService()

    async def summarize_text(
        self,
        text: str,
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
        timeout: Optional[float] = None
    ) -> str:
        """
        큐를 통해 텍스트를 요약하고 결과를 반환합니다.
        
        Args:
            text: 요약할 텍스트
            max_length: 최대 요약 길이
            min_length: 최소 요약 길이
            timeout: 작업 타임아웃 (초), None이면 dispatcher의 task_timeout 사용
        
        Returns:
            요약된 텍스트
        
        Raises:
            RuntimeError: Dispatcher가 실행 중이 아닐 때
            asyncio.TimeoutError: 작업이 타임아웃되었을 때
            asyncio.QueueFull: 큐가 가득 찼을 때
        """
        if not self.dispatcher.is_running:
            raise RuntimeError("Dispatcher가 실행 중이 아닙니다. start()를 먼저 호출하세요.")

        # Future를 사용하여 결과를 받을 수 있도록 함
        future: asyncio.Future[str] = asyncio.Future()

        # 요약 작업 코루틴 생성 (예외 처리 포함)
        async def summarize_task() -> str:
            """실제 요약 작업"""
            try:
                result = await self.summary_service.summarize(
                    text=text,
                    max_length=max_length,
                    min_length=min_length
                )
                # 결과를 Future에 설정 (Worker의 callback이 호출되기 전에 직접 설정)
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as e:
                logger.error(f"요약 작업 중 오류 발생: {e}", exc_info=True)
                # 예외도 Future에 설정
                if not future.done():
                    future.set_exception(e)
                raise

        # 콜백 함수: 결과를 Future에 설정 (이중 안전장치)
        def result_callback(result: str) -> None:
            """작업 완료 시 Future에 결과 설정"""
            if not future.done():
                future.set_result(result)

        # 큐에 작업 제출
        try:
            await self.dispatcher.submit_task(
                summarize_task(),
                callback=result_callback,
                block=True  # 큐가 가득 찰 때까지 대기
            )
        except asyncio.QueueFull:
            logger.error("큐가 가득 찼습니다. 작업을 제출할 수 없습니다.")
            raise

        # 결과 대기 (타임아웃 적용)
        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout=timeout)
            else:
                result = await future
            return result
        except asyncio.TimeoutError:
            logger.error(f"요약 작업이 {timeout}초 내에 완료되지 않았습니다.")
            raise
        except Exception as e:
            logger.error(f"요약 작업 처리 중 오류: {e}", exc_info=True)
            raise

    async def summarize_batch(
        self,
        texts: list[str],
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
        max_batch_size: int = 100,
        timeout: Optional[float] = None
    ) -> list[str]:
        """
        큐를 통해 여러 텍스트를 일괄 요약하고 결과를 반환합니다.
        
        Args:
            texts: 요약할 텍스트 리스트
            max_length: 최대 요약 길이
            min_length: 최소 요약 길이
            max_batch_size: 최대 배치 크기
            timeout: 작업 타임아웃 (초)
        
        Returns:
            요약된 텍스트 리스트
        
        Raises:
            RuntimeError: Dispatcher가 실행 중이 아닐 때
            asyncio.TimeoutError: 작업이 타임아웃되었을 때
            asyncio.QueueFull: 큐가 가득 찼을 때
        """
        if not self.dispatcher.is_running:
            raise RuntimeError("Dispatcher가 실행 중이 아닙니다. start()를 먼저 호출하세요.")

        # Future를 사용하여 결과를 받을 수 있도록 함
        future: asyncio.Future[list[str]] = asyncio.Future()

        # 배치 요약 작업 코루틴 생성 (예외 처리 포함)
        async def summarize_batch_task() -> list[str]:
            """실제 배치 요약 작업"""
            try:
                result = await self.summary_service.summarize_batch(
                    texts=texts,
                    max_length=max_length,
                    min_length=min_length,
                    max_batch_size=max_batch_size
                )
                # 결과를 Future에 설정
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as e:
                logger.error(f"배치 요약 작업 중 오류 발생: {e}", exc_info=True)
                # 예외도 Future에 설정
                if not future.done():
                    future.set_exception(e)
                raise

        # 콜백 함수: 결과를 Future에 설정 (이중 안전장치)
        def result_callback(result: list[str]) -> None:
            """작업 완료 시 Future에 결과 설정"""
            if not future.done():
                future.set_result(result)

        # 큐에 작업 제출
        try:
            await self.dispatcher.submit_task(
                summarize_batch_task(),
                callback=result_callback,
                block=True
            )
        except asyncio.QueueFull:
            logger.error("큐가 가득 찼습니다. 작업을 제출할 수 없습니다.")
            raise

        # 결과 대기 (타임아웃 적용)
        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout=timeout)
            else:
                result = await future
            return result
        except asyncio.TimeoutError:
            logger.error(f"배치 요약 작업이 {timeout}초 내에 완료되지 않았습니다.")
            raise
        except Exception as e:
            logger.error(f"배치 요약 작업 처리 중 오류: {e}", exc_info=True)
            raise

    async def summarize_with_metadata(
        self,
        text: str,
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        큐를 통해 텍스트를 요약하고 메타데이터와 함께 결과를 반환합니다.
        
        Args:
            text: 요약할 텍스트
            max_length: 최대 요약 길이
            min_length: 최소 요약 길이
            timeout: 작업 타임아웃 (초)
        
        Returns:
            {
                "summary": "요약된 텍스트",
                "original_length": 원본 텍스트 길이,
                "summary_length": 요약 텍스트 길이,
                "timestamp": 작업 완료 시간 (ISO 형식),
                "queue_size": 큐 크기
            }
        """
        start_time = datetime.now()
        original_length = len(text)

        summary = await self.summarize_text(
            text=text,
            max_length=max_length,
            min_length=min_length,
            timeout=timeout
        )

        end_time = datetime.now()
        summary_length = len(summary)

        return {
            "summary": summary,
            "original_length": original_length,
            "summary_length": summary_length,
            "timestamp": end_time.isoformat(),
            "queue_size": self.dispatcher.queue_size,
            "processing_time_seconds": (end_time - start_time).total_seconds()
        }
