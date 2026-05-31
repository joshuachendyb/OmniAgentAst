from fastapi import APIRouter
from .health import router as health_router
from .execute_tool import router as execute_tool_router
from .list_tools import router as list_tools_router
from .security_check import router as security_check_router

router = APIRouter()
router.include_router(health_router)
router.include_router(execute_tool_router)
router.include_router(list_tools_router)
router.include_router(security_check_router)

__all__ = ["router"]
