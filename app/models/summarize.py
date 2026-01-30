"""Summarize models for API requests and responses"""

from datetime import datetime, UTC
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.utils import validate_messages as validate_messages_util

if TYPE_CHECKING:
    from app.models.decision import Decision


class SummarizeRequest(BaseModel):
    """Request model for summarize endpoint"""
    messages: list[str] = Field(..., min_length=1, max_length=settings.max_messages,
                                description="List of messages to summarize")

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message content and length"""
        return validate_messages_util(v)


class SummarizeResponseMeta(BaseModel):
    """Metadata for summarization response"""
    message_count: int = Field(
        default=0,
        description="Number of messages processed"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response generation timestamp"
    )
    processing_time_ms: int = Field(
        default=0,
        description="Processing time in milliseconds"
    )


class SummarizeResponse(BaseModel):
    """Response model for summarize endpoint"""
    summary: str = Field(..., description="Summary of messages")
    time_range: str = Field(default="", description="Time range of messages")
    meta: SummarizeResponseMeta = Field(
        default_factory=SummarizeResponseMeta,
        description="Response metadata"
    )
