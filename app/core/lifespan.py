"""FastAPI application lifespan management"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.services.dispatcher import AsyncDispatcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI app.
    
    Manages startup and shutdown of application resources.
    """
    # Startup: Initialize and start dispatcher
    logger.info("Starting dispatcher...")
    dispatcher = AsyncDispatcher(
        max_workers=settings.dispatcher_max_workers,
        max_queue_size=settings.dispatcher_max_queue_size,
        task_timeout=settings.dispatcher_task_timeout
    )
    await dispatcher.start()
    app.state.dispatcher = dispatcher
    logger.info(
        f"Dispatcher started: {settings.dispatcher_max_workers} workers, "
        f"queue size {settings.dispatcher_max_queue_size}"
    )

    yield

    # Shutdown: Gracefully shutdown dispatcher
    logger.info("Shutting down dispatcher...")
    await app.state.dispatcher.shutdown(
        wait=True,
        timeout=settings.dispatcher_shutdown_timeout
    )
    logger.info("Dispatcher shutdown complete")
