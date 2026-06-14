# -*- coding: utf-8 -*-
"""
FC 消息类型安全 — Pydantic 模型

定义 OpenAI-兼容的 Function Calling 消息的 Pydantic 模型。
所有 FC 协议中的消息都使用这些类型，替代原始的 dict。

【创建时间】2026-06-11 小沈
【签名】小沈
"""

from pydantic import BaseModel
from typing import List, Optional, Union
from typing_extensions import Literal


class ToolFunction(BaseModel):
    """tool_call 中的 function 对象"""
    name: str
    arguments: str  # JSON 编码的参数字符串


class ToolCall(BaseModel):
    """FC 协议中的 tool_call 条目"""
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: str


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ToolResultMessage(BaseModel):
    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str


FcMessage = Union[SystemMessage, UserMessage, AssistantMessage, ToolResultMessage]


def message_to_dict(msg: FcMessage) -> dict:
    """将 FcMessage 转为 OpenAI 兼容的 dict（排除 None 字段）"""
    return msg.model_dump(exclude_none=True)


def dict_to_message(d: dict) -> FcMessage:
    """将 OpenAI 兼容的 dict 转回 FcMessage"""
    role = d.get("role", "")
    if role == "system":
        return SystemMessage(**d)
    elif role == "user":
        return UserMessage(**d)
    elif role == "assistant":
        return AssistantMessage(**d)
    elif role == "tool":
        return ToolResultMessage(**d)
    raise ValueError(f"Unknown role: {role}")


__all__ = [
    "ToolFunction",
    "ToolCall",
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "FcMessage",
    "message_to_dict",
    "dict_to_message",
]
