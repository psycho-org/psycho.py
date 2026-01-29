"""Error handling middleware for secure error responses"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling errors securely"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Unhandled exception: {type(e).__name__}: {e}")

            # In production, don't expose error details
            if settings.environment == "production":
                detail = "Internal server error"
            else:
                detail = str(e)

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": detail}
            )


def get_safe_error_message(error: Exception, environment: str = "development") -> str:
    """
    Get safe error message based on environment.
    
    Args:
        error: The exception
        environment: Current environment (development, staging, production)
        
    Returns:
        Safe error message
    """
    if environment == "production":
        return "An error occurred processing your request"
    return str(error)
