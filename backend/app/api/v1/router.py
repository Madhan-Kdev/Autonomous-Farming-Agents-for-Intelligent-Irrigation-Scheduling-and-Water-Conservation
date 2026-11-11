"""
API v1 router.

All v1 endpoint routers are registered here.  The prefix ``/api/v1``
is applied by the main application router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import agents, analytics, crops, et0, farms, health, irrigation, simulation

router = APIRouter()

router.include_router(health.router)
router.include_router(farms.router)
router.include_router(crops.router)
router.include_router(agents.router)
router.include_router(irrigation.router)
router.include_router(simulation.router)
router.include_router(et0.router)
router.include_router(analytics.router)
