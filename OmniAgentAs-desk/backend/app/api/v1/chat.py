"""
对话API路由
支持智谱GLM和OpenCode模型
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from app.services import AIServiceFactory

router = APIRouter()

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")

class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式返回")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2, description="温度参数")

class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool = Field(..., description="是否成功")
    content: str = Field(default="", description="回复内容")
    model: str = Field(default="", description="使用的模型")
    error: Optional[str] = Field(default=None, description="错误信息")

class ValidateResponse(BaseModel):
    """验证响应"""
    success: bool = Field(..., description="验证是否通过")
    provider: str = Field(..., description="当前使用的提供商")
    message: str = Field(default="", description="验证消息")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    发送对话请求
    
    - **messages**: 消息列表，格式为 [{"role": "user", "content": "你好"}]
    - **stream**: 是否流式返回（当前版本不支持，预留）
    - **temperature**: 创造性参数，0-2之间
    
    返回AI助手的回复内容
    """
    try:
        # 获取AI服务实例
        ai_service = AIServiceFactory.get_service()
        
        # 转换消息格式
        from app.services.base import Message
        history = []
        
        # 除最后一条消息外，其他作为历史记录
        if len(request.messages) > 1:
            for msg in request.messages[:-1]:
                history.append(Message(role=msg.role, content=msg.content))
        
        # 获取最后一条用户消息
        last_message = request.messages[-1].content if request.messages else ""
        
        # 调用AI服务
        response = await ai_service.chat(
            message=last_message,
            history=history
        )
        
        return ChatResponse(
            success=response.success,
            content=response.content,
            model=response.model,
            error=response.error
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话请求失败: {str(e)}"
        )


@router.get("/chat/validate", response_model=ValidateResponse)
async def validate_ai_service():
    """
    验证AI服务配置是否正确
    
    用于测试API密钥是否有效
    """
    try:
        # 获取当前服务
        ai_service = AIServiceFactory.get_service()
        
        # 验证服务
        is_valid = await ai_service.validate()
        
        # 获取当前提供商
        config = AIServiceFactory.load_config()
        provider = config.get("ai", {}).get("provider", "unknown")
        
        if is_valid:
            return ValidateResponse(
                success=True,
                provider=provider,
                message=f"AI服务验证成功，当前使用 {provider} 提供商"
            )
        else:
            return ValidateResponse(
                success=False,
                provider=provider,
                message=f"AI服务验证失败，请检查 {provider} 的API密钥配置"
            )
            
    except Exception as e:
        return ValidateResponse(
            success=False,
            provider="unknown",
            message=f"验证过程出错: {str(e)}"
        )


@router.post("/chat/switch/{provider}", response_model=ValidateResponse)
async def switch_ai_provider(provider: str):
    """
    切换AI提供商
    
    - **provider**: 提供商名称 (zhipuai | opencode)
    
    用于在智谱和OpenCode之间切换
    """
    try:
        # 验证提供商名称
        if provider not in ["zhipuai", "opencode"]:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的提供商: {provider}，支持的选项: zhipuai, opencode"
            )
        
        # 切换提供商
        ai_service = AIServiceFactory.switch_provider(provider)
        
        # 验证新服务
        is_valid = await ai_service.validate()
        
        if is_valid:
            return ValidateResponse(
                success=True,
                provider=provider,
                message=f"成功切换到 {provider} 提供商"
            )
        else:
            return ValidateResponse(
                success=False,
                provider=provider,
                message=f"已切换到 {provider}，但验证失败，请检查API密钥"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"切换提供商失败: {str(e)}"
        )
