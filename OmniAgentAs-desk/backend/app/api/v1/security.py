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
    score: int = Field(default=0, description="风险分数 0-10")
    risk: str = Field(default="", description="危险原因")
    message: str = Field(default="", description="风险提示信息")
    suggestion: str = Field(default="", description="建议")


@router.post("/security/check", response_model=SecurityCheckResponse)
async def check_security(request: SecurityCheckRequest):
    """
    检查命令安全性（集成CRSS评分系统）
    
    - **command**: 待检查的命令
    
    返回命令是否安全、风险分数、危险原因和建议
    """
    try:
        # 使用CRSS评分系统计算风险分数
        risk_score = calculate_risk_score(request.command)
        
        # 获取风险提示信息
        risk_message = get_risk_message(risk_score, request.command)
        
        # 检查命令安全性（黑名单检查）
        is_safe, risk = check_command_safety(request.command)
        
        # 如果黑名单检查不通过，使用黑名单原因；否则使用CRSS评分
        if not is_safe:
            # 黑名单拦截，使用黑名单的风险原因
            final_risk = risk
        else:
            # 黑名单通过，使用CRSS评分结果
            final_risk = risk_message
        
        # 根据风险分数生成建议
        suggestion = ""
        if not is_safe:
            # 黑名单拦截
            risk_level = get_command_risk_level(request.command)
            if risk_level == "critical":
                suggestion = "该操作将造成系统破坏或数据丢失，禁止执行"
            elif risk_level == "high":
                suggestion = "该操作可能导致系统不稳定或数据泄露，建议不要执行"
            elif risk_level == "medium":
                suggestion = "该操作可能存在风险，请确认后再执行"
            else:
                suggestion = "该操作可能存在风险"
        else:
            # CRSS评分建议
            if risk_score <= 2:
                suggestion = "安全操作，可以执行"
            elif risk_score <= 4:
                suggestion = "低风险操作，建议执行并记录日志"
            elif risk_score <= 6:
                suggestion = "中等风险操作，请确认后执行"
            elif risk_score <= 8:
                suggestion = "较高风险操作，需要您确认后才能执行"
            else:
                suggestion = "危险操作，系统已拦截"
        
        return SecurityCheckResponse(
            safe=is_safe,
            score=risk_score,
            risk=final_risk,
            message=risk_message,
            suggestion=suggestion
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"安全检查失败: {str(e)}"
        )
