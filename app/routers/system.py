from fastapi import APIRouter

from ..services.system_health import get_operator_status, get_system_health, get_system_tools
from ..types import OperatorStatus, SystemHealth, ToolStatus

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def system_health() -> SystemHealth:
    return get_system_health()


@router.get("/diagnostics")
def system_diagnostics() -> SystemHealth:
    return get_system_health(refresh_runtime=True)


@router.get("/tools")
def system_tools() -> list[ToolStatus]:
    return get_system_tools()


@router.get("/operator")
def system_operator() -> OperatorStatus:
    return get_operator_status()
