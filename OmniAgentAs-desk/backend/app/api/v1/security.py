"""
安全检查API路由
提供命令安全性检查接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.shell_security import (
    calculate_risk_score,
    get_risk_message
)

router = APIRouter()


class SecurityCheckRequest(BaseModel):
    """安全检查请求"""
    command: str = Field(..., description="待检查的命令")


class SecurityCheckData(BaseModel):
    """安全检查数据"""
    score: int = Field(..., description="风险分数：0-10分，整数")
    message: str = Field(..., description="用户可见的提示信息")


class SecurityCheckResponse(BaseModel):
    """安全检查响应 - 符合设计文档v1.1"""
    success: bool = Field(..., description="API是否成功调用")
    data: Optional[SecurityCheckData] = Field(None, description="检查结果数据")
    error: Optional[str] = Field(None, description="API调用失败时的错误信息")


@router.post("/security/check", response_model=SecurityCheckResponse)
async def check_security(request: SecurityCheckRequest):
    """
    检查命令安全性（CRSS评分系统）
    
    - **command**: 待检查的命令
    
    返回风险分数(0-10)和用户提示信息
    
    **响应格式**:
    ```json
    {
      "success": true,
      "data": {
        "score": 2,
        "message": "操作安全"
      }
    }
    ```
    """
    try:
        # 使用CRSS评分系统计算风险分数
        score = calculate_risk_score(request.command)
        
        # 获取用户提示信息
        message = get_risk_message(score, request.command)
        
        return SecurityCheckResponse(
            success=True,
            data=SecurityCheckData(
                score=score,
                message=message
            )
        )
        
    except Exception as e:
        return SecurityCheckResponse(
            success=False,
            error=f"安全检查失败: {str(e)}"
        )
