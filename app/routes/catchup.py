"""Generate catchup endpoint"""

import asyncio
import logging
import time
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import CatchupRequest
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/catchup", status_code=status.HTTP_200_OK)
async def generate_catchup(http_request: Request, data: CatchupRequest):
    """
    Generate catchup narrative from Discord messages (queued for background processing)
    
    Args:
        http_request: FastAPI request object
        data: CatchupRequest with list of messages
        
    Returns:
        CatchupResponse with status (queued)
    """
    start_time = time.time()
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

        # Generate catchup and extract decisions
        try:
            (narrative, key_points), decisions = await asyncio.gather(
                processor.generate_catchup(data.messages, settings.dispatcher_task_timeout),
                processor.extract_decisions(data.messages, settings.dispatcher_task_timeout),
                return_exceptions=True
            )

            # Handle exceptions from gather
            if isinstance(narrative, Exception):
                logger.error(f"Catchup generation failed: {narrative}")
                raise narrative

            if isinstance(decisions, Exception):
                logger.warning(f"Decision extraction failed during catchup: {decisions}")
                decisions = []
            else:
                # Extract the decisions from the tuple result
                if isinstance(narrative, tuple):
                    narrative, key_points = narrative

            logger.info(
                f"Catchup generation completed: {len(narrative)} chars, {len(key_points)} key points, {len(decisions)} decisions")
        except asyncio.TimeoutError:
            logger.error(f"Catchup generation timeout after {settings.dispatcher_task_timeout}s")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Catchup processing timeout"
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
            logger.error(f"Catchup processing failed: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Catchup processing failed"
            )

        processing_time_ms = int((time.time() - start_time) * 1000)
        timestamp = datetime.now(UTC)

        # Add narrative and key_points to each decision
        decisions_with_catchup = [
            {
                **decision.model_dump(),
                "summary": narrative,
                "time_range": ", ".join(key_points) if key_points else ""
            }
            for decision in decisions
        ]

        return {
            "narrative": narrative,
            "key_points": key_points,
            "data": decisions_with_catchup,
            "meta": {
                "timestamp": timestamp,
                "processing_time_ms": processing_time_ms
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_catchup endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
