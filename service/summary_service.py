"""
요약 서비스 - 채팅 이력 기반 요약 파이프라인
"""

from __future__ import annotations

from infrastructure.summary import SummaryAnalyzer
from service.discord_chat_service import DiscordChatService

# 채팅 요약용 기본값 (일반 요약보다 길게)
CHAT_DEFAULT_MAX_LENGTH = 200
CHAT_DEFAULT_MIN_LENGTH = 50


class SummaryService:
    """Discord Bot용 요약 서비스 - 채팅 이력 기반 요약"""
    
    def __init__(self, chat_service: DiscordChatService | None = None):
        self.analyzer = SummaryAnalyzer()
        self.chat_service = chat_service
    
    async def summarize(
        self,
        text: str,
        max_length: int | None = None,
        min_length: int | None = None,
    ) -> str:
        """텍스트 요약"""
        return self.analyzer.summarize(text, max_length, min_length)
    
    async def summarize_batch(
        self,
        texts: list[str],
        max_length: int | None = None,
        min_length: int | None = None,
        max_batch_size: int = 100,
    ) -> list[str]:
        """여러 텍스트 일괄 요약"""
        return self.analyzer.summarize_batch(texts, max_length, min_length, max_batch_size)
    
    async def summarize_channel_chat(
        self,
        channel_id: int,
        limit: int = 50,
        max_length: int | None = None,
        min_length: int | None = None,
    ) -> dict[str, str]:
        """
        특정 채널의 채팅 이력을 요약하는 파이프라인
        
        Args:
            channel_id: 채널 ID
            limit: 요약할 최근 메시지 개수
            max_length: 최대 요약 길이, None이면 기본값 사용
            min_length: 최소 요약 길이, None이면 기본값 사용
        
        Returns:
            {"summary": "요약 내용", "message_count": 메시지 개수}
        """
        if not self.chat_service:
            raise ValueError("chat_service가 설정되지 않았습니다.")
        
        # 기본값 설정
        max_length = max_length if max_length is not None else CHAT_DEFAULT_MAX_LENGTH
        min_length = min_length if min_length is not None else CHAT_DEFAULT_MIN_LENGTH
        
        # 1. 채팅 서비스에서 메시지 텍스트 가져오기
        chat_text = self.chat_service.get_messages_text_by_channel(
            channel_id=channel_id,
            limit=limit,
            include_author=True,
        )
        
        if not chat_text or len(chat_text.strip()) < min_length:
            return {
                "summary": "요약할 충분한 대화가 없습니다.",
                "message_count": 0,
            }
        
        # 2. LGAI EXAONE 모델로 요약
        summary = self.analyzer.summarize(
            chat_text,
            max_length=max_length,
            min_length=min_length,
        )
        
        message_count = len([
            m for m in self.chat_service.messages
            if m["channel_id"] == channel_id
        ][-limit:])
        
        return {
            "summary": summary,
            "message_count": message_count,
        }
    
    async def summarize_all_chat(
        self,
        limit: int = 100,
        max_length: int | None = None,
        min_length: int | None = None,
    ) -> dict[str, str]:
        """
        모든 채팅 이력을 요약하는 파이프라인
        
        Args:
            limit: 요약할 최근 메시지 개수
            max_length: 최대 요약 길이, None이면 기본값 사용
            min_length: 최소 요약 길이, None이면 기본값 사용
        
        Returns:
            {"summary": "요약 내용", "message_count": 메시지 개수}
        """
        if not self.chat_service:
            raise ValueError("chat_service가 설정되지 않았습니다.")
        
        # 기본값 설정
        max_length = max_length if max_length is not None else CHAT_DEFAULT_MAX_LENGTH
        min_length = min_length if min_length is not None else CHAT_DEFAULT_MIN_LENGTH
        
        # 1. 채팅 서비스에서 모든 메시지 텍스트 가져오기
        chat_text = self.chat_service.get_all_messages_text(
            limit=limit,
            include_author=True,
        )
        
        if not chat_text or len(chat_text.strip()) < min_length:
            return {
                "summary": "요약할 충분한 대화가 없습니다.",
                "message_count": 0,
            }
        
        # 2. LGAI EXAONE 모델로 요약
        summary = self.analyzer.summarize(
            chat_text,
            max_length=max_length,
            min_length=min_length,
        )
        
        message_count = min(limit, len(self.chat_service.messages))
        
        return {
            "summary": summary,
            "message_count": message_count,
        }
