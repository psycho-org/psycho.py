"""Health check and info endpoints"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "Psycho AI Server"}


@router.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Psycho AI Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "summarize": "POST /api/summarize",
            "extract_decisions": "POST /api/decisions",
            "generate_catchup": "POST /api/catchup"
        },
        "docs": "/docs"
    }
