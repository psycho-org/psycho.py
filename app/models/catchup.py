"""Catchup models for API requests and responses"""

from datetime import datetime, UTC

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.utils import validate_messages as validate_messages_util


class CatchupRequest(BaseModel):
    """Request model for generate catchup endpoint"""
    messages: list[str] = Field(..., min_length=1, max_length=settings.max_messages,
                                description="List of messages to generate catchup from")

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message content and length"""
        return validate_messages_util(v)


class CatchupResponseMeta(BaseModel):
    """Metadata for catchup generation response"""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response generation timestamp"
    )
    processing_time_ms: int = Field(
        default=0,
        description="Processing time in milliseconds"
    )


class CatchupResponse(BaseModel):
    """Response model for generate catchup endpoint"""
    narrative: str = Field(..., description="Catchup narrative")
    key_points: list[str] = Field(default_factory=list, description="Key points from conversation")
    meta: CatchupResponseMeta = Field(
        default_factory=CatchupResponseMeta,
        description="Response metadata"
    )
