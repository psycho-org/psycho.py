"""Generate catchup endpoint"""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.middleware import get_safe_error_message
from app.models import CatchupRequest, CatchupResponse
from app.services.ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Processing"])


@router.post("/catchup", response_model=CatchupResponse)
async def generate_catchup(request: CatchupRequest):
    """
    Generate catchup narrative from Discord messages
    
    Args:
        request: CatchupRequest with list of messages
        
    Returns:
        CatchupResponse with narrative and key points
    """
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        logger.info(f"Processing {len(request.messages)} messages for catchup generation")

        narrative, key_points = AIProcessor.generate_catchup(request.messages)

        return CatchupResponse(
            narrative=narrative,
            key_points=key_points
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_catchup endpoint: {type(e).__name__}: {e}")
        safe_message = get_safe_error_message(e, settings.environment)
        raise HTTPException(status_code=500, detail=safe_message)
