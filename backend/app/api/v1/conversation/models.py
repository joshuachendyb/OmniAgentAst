# -*- coding: utf-8 -*-
"""
ExecutionStepsUpdate — 从 conversation.py 拷出

拷贝来源: conversation.py 第180-194行
"""

from typing import Optional
from pydantic import BaseModel, Field


class ExecutionStepsUpdate(BaseModel):
    """拷贝自 conversation.py 第180-194行"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID")
