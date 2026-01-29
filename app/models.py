"""Pydantic models for API requests and responses"""

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class SummarizeRequest(BaseModel):
    """Request model for summarize endpoint"""
    messages: list[str] = Field(..., min_length=1, max_length=settings.max_messages,
                                description="List of messages to summarize")

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message content and length"""
        for msg in v:
            if len(msg) > settings.max_message_length:
                raise ValueError(f"Message exceeds max length of {settings.max_message_length} characters")
            if len(msg) == 0:
                raise ValueError("Empty messages are not allowed")

        # Check total character count
        total_chars = sum(len(msg) for msg in v)
        if total_chars > settings.max_total_characters:
            raise ValueError(f"Total message content exceeds max of {settings.max_total_characters} characters")

        return v


class SummarizeResponse(BaseModel):
    """Response model for summarize endpoint"""
    summary: str = Field(..., description="Summary of messages")
    message_count: int = Field(..., description="Number of messages processed")
    time_range: str = Field(default="", description="Time range of messages")


class Decision(BaseModel):
    """Single decision extracted from messages"""
    title: str = Field(..., description="Decision title")
    owner: str = Field(..., description="Person responsible for decision")
    deadline: str = Field(..., description="Decision deadline")
    context: str = Field(..., description="Context/background of decision")


class DecisionRequest(BaseModel):
    """Request model for extract decisions endpoint"""
    messages: list[str] = Field(..., min_length=1, max_length=settings.max_messages,
                                description="List of messages to analyze")

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message content and length"""
        for msg in v:
            if len(msg) > settings.max_message_length:
                raise ValueError(f"Message exceeds max length of {settings.max_message_length} characters")
            if len(msg) == 0:
                raise ValueError("Empty messages are not allowed")

        total_chars = sum(len(msg) for msg in v)
        if total_chars > settings.max_total_characters:
            raise ValueError(f"Total message content exceeds max of {settings.max_total_characters} characters")

        return v


class DecisionResponse(BaseModel):
    """Response model for extract decisions endpoint"""
    decisions: list[Decision] = Field(default_factory=list, description="Extracted decisions")


class CatchupRequest(BaseModel):
    """Request model for generate catchup endpoint"""
    messages: list[str] = Field(..., min_length=1, max_length=settings.max_messages,
                                description="List of messages to generate catchup from")

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message content and length"""
        for msg in v:
            if len(msg) > settings.max_message_length:
                raise ValueError(f"Message exceeds max length of {settings.max_message_length} characters")
            if len(msg) == 0:
                raise ValueError("Empty messages are not allowed")

        total_chars = sum(len(msg) for msg in v)
        if total_chars > settings.max_total_characters:
            raise ValueError(f"Total message content exceeds max of {settings.max_total_characters} characters")

        return v


class CatchupResponse(BaseModel):
    """Response model for generate catchup endpoint"""
    narrative: str = Field(..., description="Catchup narrative")
    key_points: list[str] = Field(default_factory=list, description="Key points from conversation")
