"""
安全检查API路由
提供命令安全性检查接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.shell_security import (
    check_command_safety, 
    get_command_risk_level,
    calculate_risk_score,
    get_risk_message
)

router = APIRouter()


class SecurityCheckRequest(BaseModel):
    """安全检查请求"""
    command: str = Field(..., description="待检查的命令")


class SecurityCheckResponse(BaseModel):
    """安全检查响应"""
    safe: bool = Field(..., description="命令是否安全")
    risk: str = Field(default="", description="危险原因")
    suggestion: str = Field(default="", description="建议")


@router.post("/security/check", response_model=SecurityCheckResponse)
async def check_security(request: SecurityCheckRequest):
    """
    检查命令安全性
    
    - **command**: 待检查的命令
    
    返回命令是否安全，以及危险原因和建议
    """
    try:
        # 检查命令安全性
        is_safe, risk = check_command_safety(request.command)
        
        # 获取风险等级
        risk_level = get_command_risk_level(request.command)
        
        # 生成建议
        suggestion = ""
        if not is_safe:
            if risk_level == "critical":
                suggestion = "该操作将造成系统破坏或数据丢失，禁止执行"
            elif risk_level == "high":
                suggestion = "该操作可能导致系统不稳定或数据泄露，建议不要执行"
            elif risk_level == "medium":
                suggestion = "该操作可能存在风险，请确认后再执行"
            else:
                suggestion = "该操作可能存在风险"
        
        return SecurityCheckResponse(
            safe=is_safe,
            risk=risk,
            suggestion=suggestion
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"安全检查失败: {str(e)}"
        )
