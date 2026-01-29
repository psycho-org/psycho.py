"""Extract decisions endpoint"""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import DecisionRequest, DecisionResponse
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/decisions", response_model=DecisionResponse)
async def extract_decisions(request: DecisionRequest):
    """
    Extract decisions from Discord messages
    
    Args:
        request: DecisionRequest with list of messages
        
    Returns:
        DecisionResponse with extracted decisions
    """
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        logger.info(f"Processing {len(request.messages)} messages for decision extraction")

        decisions = AIProcessor.extract_decisions(request.messages)

        return DecisionResponse(decisions=decisions)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract_decisions endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
