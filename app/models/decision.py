"""Decision models for API requests and responses"""

from datetime import datetime, UTC
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.config import settings
from app.utils import validate_messages as validate_messages_util


class DecisionStatus(str, Enum):
    """Decision execution status"""
    OPEN = "open"  # Not yet started
    BLOCKED = "blocked"  # Blocked by external factors
    IN_PROGRESS = "in_progress"  # Currently in progress
    COMPLETED = "completed"  # Completed
    CANCELLED = "cancelled"  # Cancelled


class Decision(BaseModel):
    """Single decision extracted from messages with extended metadata"""

    # Pydantic v2 configuration
    model_config = ConfigDict(use_enum_values=True)

    # Core fields
    title: str = Field(
        ...,
        max_length=200,
        description="Decision title - should be clear and actionable"
    )
    owner: str = Field(
        ...,
        description="Person or team responsible for execution"
    )
    deadline: str = Field(
        default="",
        description="Deadline in ISO format (YYYY-MM-DD or ISO 8601)"
    )
    context: str = Field(
        ...,
        description="Background, rationale, and impact of the decision"
    )

    time_range: str = Field(
        default="",
        description="Time range of the conversation"
    )

    # Status tracking
    status: DecisionStatus = Field(
        default=DecisionStatus.OPEN,
        description="Current execution status"
    )

    # Metadata
    priority: str = Field(
        default="medium",
        description="Priority level: low, medium, high, critical"
    )
    category: Optional[str] = Field(
        default=None,
        description="Category: schedule, technical, business, policy, resource"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this decision was created/extracted"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp"
    )

    # Additional notes
    notes: str = Field(
        default="",
        description="Progress notes or updates on decision"
    )


class DecisionRequest(BaseModel):
    """Request model for extract decisions endpoint"""
    messages: list[str] = Field(..., min_length=1, max_length=settings.max_messages,
                                description="List of messages to analyze")

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message content and length"""
        return validate_messages_util(v)


class DecisionResponseMeta(BaseModel):
    """Metadata for decision extraction response"""
    count: int = Field(
        default=0,
        description="Total number of decisions extracted"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response generation timestamp"
    )
    processing_time_ms: int = Field(
        default=0,
        description="Processing time in milliseconds"
    )


class DecisionResponse(BaseModel):
    """Response model for extract decisions endpoint"""
    data: list[Decision] = Field(
        default_factory=list,
        description="Extracted decisions with status tracking"
    )
    meta: DecisionResponseMeta = Field(
        default_factory=DecisionResponseMeta,
        description="Response metadata"
    )
