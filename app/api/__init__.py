from fastapi import APIRouter

from .stats_core import router as core_router
from .users import router as users_router
from .stations import router as stations_router
from .models import router as models_router
from .drivers import router as drivers_router
from .executive_api import router as executive_router
from .auth_api import router as auth_router
from .energy import router as energy_router

router = APIRouter()
router.include_router(core_router)
router.include_router(users_router)
router.include_router(stations_router)
router.include_router(models_router)
router.include_router(drivers_router)
router.include_router(executive_router)
router.include_router(auth_router)
router.include_router(energy_router)
