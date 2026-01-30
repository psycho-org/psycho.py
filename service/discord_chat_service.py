"""
Discord 채팅 관련 서비스 - 대화 수집, 출력, 분석, 요약
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class DiscordChatService:
    """Discord 채팅 관련 비즈니스 로직"""
    
    def __init__(self):
        self.messages: list[dict[str, Any]] = []
    
    def add_message(
        self,
        *,
        guild_id: int | None,
        channel_id: int,
        user_id: int,
        author_name: str,
        content: str,
        created_at: datetime,
    ) -> None:
        """메시지를 서비스에 추가"""
        self.messages.append({
            "guild_id": guild_id,
            "channel_id": channel_id,
            "user_id": user_id,
            "author_name": author_name,
            "content": content,
            "created_at": created_at,
        })
    
    def format_message_for_display(self, message: dict[str, Any]) -> str:
        """메시지를 출력용으로 포맷팅"""
        time_str = message["created_at"].strftime("%H:%M:%S")
        author = message["author_name"]
        content = message["content"][:200]
        return f"[{time_str}] {author}: {content}"
    
    def display_realtime_message(
        self,
        *,
        guild_name: str,
        channel_name: str,
        channel_id: int | None = None,
        author_name: str,
        content: str,
        created_at: datetime,
    ) -> None:
        """실시간 메시지를 콘솔에 출력"""
        time_str = created_at.strftime("%H:%M:%S")
        content_preview = content[:200]
        
        # 채널 정보를 더 명확하게 표시
        channel_info = channel_name
        if channel_id:
            channel_info = f"{channel_name} (ID: {channel_id})"
        
        print(f"\n💬 [{time_str}] 📍 {guild_name} > {channel_info}")
        print(f"   👤 {author_name}: {content_preview}")
        if len(content) > 200:
            print(f"   ... (전체 {len(content)}자)")
    
    def format_channel_info(
        self,
        *,
        guild_name: str,
        guild_id: int,
        member_count: int,
        channels: list[dict[str, Any]],
    ) -> str:
        """채널 정보를 포맷팅하여 반환"""
        lines = [
            "=" * 60,
            "📋 채팅방 정보 및 최근 대화",
            "=" * 60,
            f"\n🏠 서버: {guild_name} (ID: {guild_id})",
            f"   멤버 수: {member_count}",
        ]
        
        for channel in channels:
            channel_name = channel.get("name", "알 수 없음")
            channel_id = channel.get("id", 0)
            topic = channel.get("topic") or "(없음)"
            can_read = channel.get("can_read", False)
            recent_messages = channel.get("recent_messages", [])
            
            lines.append(f"\n   📢 채널: #{channel_name} (ID: {channel_id})")
            lines.append(f"      주제: {topic}")
            
            if not can_read:
                lines.append(f"      상태: 권한 없음")
            elif recent_messages:
                lines.append(f"      최근 대화 ({len(recent_messages)}개):")
                for msg in recent_messages[:5]:  # 최대 5개만 표시
                    time_str = msg.get("time", "")
                    author = msg.get("author", "")
                    content = msg.get("content", "")
                    lines.append(f"        [{time_str}] {author}: {content}")
            else:
                lines.append(f"      최근 대화 없음")
        
        lines.append("\n" + "=" * 60 + "\n")
        return "\n".join(lines)
    
    def format_messages_for_discord(
        self,
        messages: list[dict[str, Any]],
        limit: int = 15,
    ) -> list[str]:
        """Discord 임베드용으로 메시지 포맷팅"""
        lines = []
        for i, msg in enumerate(messages[:limit], 1):
            author = msg.get("author", "알 수 없음")
            time_str = msg.get("time", "")
            content = msg.get("content", "")
            lines.append(f"{i}. **{author}** ({time_str})\n   {content}")
        return lines
    
    def format_channels_for_discord(
        self,
        channels: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[str]:
        """Discord 임베드용으로 채널 정보 포맷팅"""
        lines = []
        for channel in channels[:limit]:
            channel_name = channel.get("name", "알 수 없음")
            channel_id = channel.get("id", 0)
            status = channel.get("status", "알 수 없음")
            topic = channel.get("topic", "(없음)")
            
            lines.append(
                f"**#{channel_name}**\n"
                f"ID: `{channel_id}`\n"
                f"상태: {status}\n"
                f"주제: {topic[:50] + '...' if len(topic) > 50 else topic}"
            )
        return lines
    
    def get_recent_messages(self, limit: int = 20) -> list[dict[str, Any]]:
        """최근 메시지 가져오기"""
        return self.messages[-limit:]
    
    def get_messages_by_channel(self, channel_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """특정 채널의 메시지 가져오기"""
        channel_messages = [m for m in self.messages if m["channel_id"] == channel_id]
        return channel_messages[-limit:]
    
    def get_messages_text_by_channel(
        self,
        channel_id: int,
        limit: int = 50,
        include_author: bool = True,
    ) -> str:
        """특정 채널의 메시지들을 텍스트로 변환 (요약용)"""
        channel_messages = [m for m in self.messages if m["channel_id"] == channel_id]
        channel_messages = channel_messages[-limit:]
        
        if not channel_messages:
            return ""
        
        lines = []
        for msg in channel_messages:
            author = msg.get("author_name", "알 수 없음")
            content = msg.get("content", "")
            time_str = msg.get("created_at", datetime.now()).strftime("%Y-%m-%d %H:%M")
            
            if include_author:
                lines.append(f"[{time_str}] {author}: {content}")
            else:
                lines.append(content)
        
        return "\n".join(lines)
    
    def get_all_messages_text(
        self,
        limit: int = 100,
        include_author: bool = True,
    ) -> str:
        """모든 메시지를 텍스트로 변환 (요약용)"""
        recent_messages = self.messages[-limit:] if limit else self.messages
        
        if not recent_messages:
            return ""
        
        lines = []
        for msg in recent_messages:
            author = msg.get("author_name", "알 수 없음")
            content = msg.get("content", "")
            time_str = msg.get("created_at", datetime.now()).strftime("%Y-%m-%d %H:%M")
            
            if include_author:
                lines.append(f"[{time_str}] {author}: {content}")
            else:
                lines.append(content)
        
        return "\n".join(lines)
