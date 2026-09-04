# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 - 小欧 - S1(10.1.4②): ChatRequest 增 context_link_mode(任务上下文链, 默认 independent 新任务/linked 续聊需显式),
#   白名单校验在 orchestrator(10.1.4⑧), 本处仅 DTO 默认值定义
"""
models — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第152-166行
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """拷贝自 chat_router.py 第152-155行"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """拷贝自 chat_router.py 第158-166行"""
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式返回")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2, description="温度参数")
    provider: Optional[str] = Field(default=None, description="前端指定的提供商")
    model: Optional[str] = Field(default=None, description="前端指定的模型")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    context_link_mode: Optional[str] = Field(default="independent",
        description="任务类型: independent新任务(默认)/linked续聊需显式")  # 10.1.4② 任务上下文链
