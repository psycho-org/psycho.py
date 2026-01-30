"""Summarize endpoint"""

import asyncio
import logging
import time
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import SummarizeRequest, SummarizeResponse, SummarizeResponseMeta
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/summarize", response_model=SummarizeResponse, status_code=status.HTTP_200_OK)
async def summarize(request: Request, data: SummarizeRequest):
    """
    Summarize Discord messages and extract decisions.
    
    Args:
        request: FastAPI request object
        data: SummarizeRequest with list of messages
        
    Returns:
        JSON response with summary and decisions
    """
    start_time = time.time()
    try:
        if not data.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        logger.info(f"Processing {len(data.messages)} messages for summarization and decision extraction")

        # Get dispatcher from app state
        dispatcher = request.app.state.dispatcher
        if not dispatcher or not dispatcher.is_running:
            raise HTTPException(status_code=503, detail="Service unavailable")

        # Create AIProcessor with dispatcher
        processor = AIProcessor(dispatcher=dispatcher)

        try:
            summary, time_range = await processor.summarize(
                data.messages,
                timeout=settings.dispatcher_task_timeout
            )
            # Log summary content (truncated to prevent oversized logs)
            max_log_len = 2000
            preview = summary if len(summary) <= max_log_len else summary[:max_log_len] + "... [truncated]"
            logger.info(
                "Summary completed: %s chars, time_range=%s, preview=\n%s",
                len(summary), time_range, preview
            )
        except asyncio.TimeoutError:
            logger.error(f"Analysis timeout after {settings.dispatcher_task_timeout}s")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Processing timeout"
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
            logger.error(f"Analysis failed: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Processing failed"
            )

        processing_time_ms = int((time.time() - start_time) * 1000)
        timestamp = datetime.now(UTC)

        return SummarizeResponse(
            summary=summary,
            time_range=time_range,
            meta=SummarizeResponseMeta(
                message_count=len(data.messages),
                timestamp=timestamp,
                processing_time_ms=processing_time_ms
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in summarize endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
