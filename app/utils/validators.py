"""Validation utilities for API requests"""

from app.config import settings


def validate_messages(messages: list[str]) -> list[str]:
    """
    Validate message content and length.
    
    Args:
        messages: List of messages to validate
        
    Returns:
        Validated messages list
        
    Raises:
        ValueError: If validation fails
    """
    if not messages:
        raise ValueError("Messages list cannot be empty")

    for msg in messages:
        if len(msg) > settings.max_message_length:
            raise ValueError(f"Message exceeds max length of {settings.max_message_length} characters")
        if len(msg) == 0:
            raise ValueError("Empty messages are not allowed")

    # Check total character count
    total_chars = sum(len(msg) for msg in messages)
    if total_chars > settings.max_total_characters:
        raise ValueError(f"Total message content exceeds max of {settings.max_total_characters} characters")

    return messages
