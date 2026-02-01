"""Extract decisions endpoint (specialized)

Provides a dedicated endpoint to extract decisions with independent
timeout/retry policy from summarize.
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status, Query

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import DecisionRequest, DecisionResponse, DecisionResponseMeta
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/decisions", response_model=DecisionResponse, status_code=status.HTTP_200_OK)
async def extract_decisions(
    http_request: Request,
    data: DecisionRequest,
    timeout_seconds: Optional[float] = Query(
        default=None,
        ge=1.0,
        description="Per-request timeout in seconds. None waits until completion."
    ),
    retry: int = Query(
        default=0,
        ge=0,
        le=2,
        description="Number of additional retries if no decisions are extracted."
    ),
    require_non_empty: bool = Query(
        default=False,
        description="If true, perform up to `retry` retries when the result is empty."
    ),
) -> DecisionResponse:
    """
    Extract decisions from messages (dedicated endpoint).

    Query controls allow longer waits and targeted retries without
    impacting summarize SLOs.
    """
    start_time = time.time()
    try:
        if not data.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        dispatcher = http_request.app.state.dispatcher
        if not dispatcher or not dispatcher.is_running:
            raise HTTPException(status_code=503, detail="Service unavailable")

        processor = AIProcessor(dispatcher=dispatcher)

        # Determine timeout to use
        eff_timeout = timeout_seconds if timeout_seconds is not None else settings.dispatcher_task_timeout

        attempts = 0
        last_error: Optional[Exception] = None

        while True:
            attempts += 1
            try:
                decisions = await processor.extract_decisions(data.messages, timeout=eff_timeout)
                logger.info("Decisions attempt %s: %s items", attempts, len(decisions))
                # Clear any previous error on successful attempt
                last_error = None
            except asyncio.TimeoutError:
                logger.error("Decisions timeout on attempt %s after %ss", attempts, eff_timeout)
                last_error = HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Decision extraction processing timeout"
                )
                decisions = []
            except asyncio.QueueFull:
                logger.error("Task queue is full on attempt %s", attempts)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="System is overloaded. Please try again later."
                )
            except RuntimeError as e:
                logger.error("Dispatcher error on attempt %s: %s", attempts, e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service temporarily unavailable"
                )
            except Exception as e:
                logger.error("Decision extraction failed on attempt %s: %s: %s", attempts, type(e).__name__, e,
                             exc_info=True)
                last_error = HTTPException(status_code=500, detail="Decision extraction processing failed")
                decisions = []

            # Retry policy
            if decisions or not require_non_empty or attempts > retry:
                break
            else:
                logger.info("Empty result; retrying (%s/%s)", attempts - 1, retry)

        if not decisions and last_error:
            # Still empty and require_non_empty was true -> return last error
            raise last_error

        processing_time_ms = int((time.time() - start_time) * 1000)
        return DecisionResponse(
            data=decisions,
            meta=DecisionResponseMeta(
                count=len(decisions),
                processing_time_ms=processing_time_ms
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in /api/decisions endpoint: %s: %s", type(e).__name__, e)
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
