from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

class SecurityCheckRequest(BaseModel):
    """安全检查请求"""
    command: str = Field(..., description="要检查的命令")

@router.post("/security/check")
async def security_check(request: SecurityCheckRequest):
    """
    检查命令安全性

    Args:
        request: 安全检查请求，包含command字段

    Returns:
        dict: 安全检查结果，包含success、data字段
    """
    try:
        from app.services.tools.shell.command_security import CommandSecurity

        command = request.command
        security = CommandSecurity()
        result = security.check_command(command)

        return {
            "success": True,
            "data": {
                "score": result.get("score", 0),
                "message": result.get("message", ""),
                "is_safe": result.get("is_safe", True),
                "risk_level": result.get("risk_level", "low")
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
