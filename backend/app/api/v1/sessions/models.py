"""
sessions 数据模型

迁移来源: conversation/models.py (M-15 修正)
迁移人: 小欧 - 2026-07-10
"""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class ExecutionStep:
    """执行步骤数据模型"""
    def __init__(self, step_type: str, content: str = "", tool: str = "",
                 params: Optional[Dict] = None, result: Any = None, timestamp: int = 0):
        self.type = step_type
        self.content = content
        self.tool = tool
        self.params = params or {}
        self.result = result
        self.timestamp = timestamp

    def to_dict(self):
        data = {"type": self.type, "timestamp": self.timestamp}
        if self.content:
            data["content"] = self.content
        if self.tool:
            data["tool"] = self.tool
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        return data


class ExecutionStepsUpdate(BaseModel):
    """执行步骤更新请求体"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID")
