from fastapi import APIRouter
from .health import router as health_router
from .execute_tool import router as execute_tool_router

router = APIRouter()
router.include_router(health_router)
router.include_router(execute_tool_router)

__all__ = ["router"]
