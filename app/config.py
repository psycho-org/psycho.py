"""Application configuration and security settings"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with security configurations"""

    # App settings
    app_name: str = "Psycho AI Server"
    app_version: str = "1.0.0"
    environment: str = "development"  # development, staging, production

    # Security
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="CORS allowed origins as JSON list or comma-separated"
    )
    api_key: str = ""  # Set via environment variable for production

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

    # Input validation
    max_messages: int = 1000  # Maximum number of messages per request
    max_message_length: int = 5000  # Maximum length of a single message
    max_total_characters: int = 100000  # Maximum total characters in request

    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = True

    # Dispatcher settings
    dispatcher_max_workers: int = Field(
        default=5,
        ge=1  # Minimum 1 worker
    )
    dispatcher_max_queue_size: int = Field(
        default=100,
        ge=1  # Minimum queue size of 1
    )
    # If None, worker will wait indefinitely for each task (no timeout)
    dispatcher_task_timeout: Optional[float] = Field(
        default=60.0,
        description="Per-task timeout in seconds. None disables timeout."
    )
    dispatcher_shutdown_timeout: float = Field(
        default=30.0,
        ge=1.0,  # Minimum 1 second
        le=120.0  # Maximum 2 minutes
    )

    @field_validator('dispatcher_task_timeout')
    @classmethod
    def validate_task_timeout(cls, v):
        if v is None:
            return v
        if v > 300:
            raise ValueError("Task timeout cannot exceed 300 seconds (5 minutes)")
        if v < 1:
            raise ValueError("Task timeout must be at least 1 second")
        return v

    @field_validator('dispatcher_shutdown_timeout')
    @classmethod
    def validate_shutdown_timeout(cls, v):
        if v > 120:
            raise ValueError("Shutdown timeout cannot exceed 120 seconds (2 minutes)")
        if v < 1:
            raise ValueError("Shutdown timeout must be at least 1 second")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
