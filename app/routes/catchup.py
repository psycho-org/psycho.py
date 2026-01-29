"""Generate catchup endpoint"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import CatchupRequest, CatchupResponse
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/catchup", response_model=CatchupResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_catchup(http_request: Request, data: CatchupRequest):
    """
    Generate catchup narrative from Discord messages (queued for background processing)
    
    Args:
        http_request: FastAPI request object
        data: CatchupRequest with list of messages
        
    Returns:
        CatchupResponse with status (queued)
    """
    try:
        if not data.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        logger.info(f"Processing {len(data.messages)} messages for catchup generation")

        # Get dispatcher from app state
        dispatcher = http_request.app.state.dispatcher
        if not dispatcher or not dispatcher.is_running:
            raise HTTPException(status_code=503, detail="Service unavailable")

        # Create AIProcessor with dispatcher
        processor = AIProcessor(dispatcher=dispatcher)

        # Generate catchup and return with actual results
        try:
            narrative, key_points = await processor.generate_catchup(
                data.messages,
                timeout=settings.dispatcher_task_timeout
            )
            logger.info(f"Catchup generation completed: {len(narrative)} chars, {len(key_points)} key points")
        except asyncio.TimeoutError:
            logger.error(f"Catchup generation timeout after {settings.dispatcher_task_timeout}s")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Catchup generation processing timeout"
            )
        except asyncio.QueueFull:
            logger.error("Task queue is full")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="System is overloaded. Please try again later."
            )
        except RuntimeError as e:
            logger.error(f"Dispatcher error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable"
            )
        except Exception as e:
            logger.error(f"Catchup generation failed: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Catchup generation processing failed"
            )

        return CatchupResponse(narrative=narrative, key_points=key_points)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_catchup endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
