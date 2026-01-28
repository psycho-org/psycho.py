"""Summarize endpoint"""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import SummarizeRequest, SummarizeResponse
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """
    Summarize Discord messages
    
    Args:
        request: SummarizeRequest with list of messages
        
    Returns:
        SummarizeResponse with summary and metadata
    """
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        logger.info(f"Processing {len(request.messages)} messages for summarization")

        summary, time_range = AIProcessor.summarize(request.messages)

        return SummarizeResponse(
            summary=summary,
            message_count=len(request.messages),
            time_range=time_range
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in summarize endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
