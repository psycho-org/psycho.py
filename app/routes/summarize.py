"""Summarize endpoint"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import SummarizeRequest, SummarizeResponse
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/summarize", response_model=SummarizeResponse, status_code=status.HTTP_202_ACCEPTED)
async def summarize(request: Request, data: SummarizeRequest):
    """
    Summarize Discord messages (queued for background processing)
    
    Args:
        request: FastAPI request object
        data: SummarizeRequest with list of messages
        
    Returns:
        SummarizeResponse with status (queued)
    """
    try:
        if not data.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        logger.info(f"Processing {len(data.messages)} messages for summarization")

        # Get dispatcher from app state
        dispatcher = request.app.state.dispatcher
        if not dispatcher or not dispatcher.is_running:
            raise HTTPException(status_code=503, detail="Service unavailable")

        # Create AIProcessor with dispatcher
        processor = AIProcessor(dispatcher=dispatcher)

        # Process summarization
        try:
            summary, time_range = await processor.summarize(
                data.messages,
                timeout=settings.dispatcher_task_timeout
            )
            logger.info(f"Summarization completed: {len(summary)} chars")
        except asyncio.TimeoutError:
            logger.error(f"Summarization timeout after {settings.dispatcher_task_timeout}s")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Summarization processing timeout"
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
            logger.error(f"Summarization failed: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Summarization processing failed"
            )

        return SummarizeResponse(
            summary=summary,
            message_count=len(data.messages),
            time_range=time_range
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in summarize endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
