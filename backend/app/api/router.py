"""
Main API router.

Mounts all versioned routers.  Add new API versions here.
"""

from fastapi import APIRouter

from app.api.v1 import router as v1_router
from app.core.config import settings

router = APIRouter()

router.include_router(v1_router.router, prefix=settings.API_V1_PREFIX)
