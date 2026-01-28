"""Application configuration and security settings"""

from pydantic import Field
from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
