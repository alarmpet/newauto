from fastapi import APIRouter

from ..services.system_health import get_system_health
from ..types import SystemHealth

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def system_health() -> SystemHealth:
    return get_system_health()
