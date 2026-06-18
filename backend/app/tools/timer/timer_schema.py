# -*- coding: utf-8 -*-
"""
Timer Schema - 定时器工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容
"""

from pydantic import BaseModel, Field
from typing import Optional


class TimerSetInput(BaseModel):
    delay: float = Field(
        ..., ge=1, le=86400,
        description="延迟秒数(1~86400即最长24小时)。必填参数"
    )
    callback: str = Field(
        ..., description="定时器触发内容(文本消息)。必填参数"
    )


class TimerClearInput(BaseModel):
    timer_id: str = Field(
        ..., description="定时器ID,由 timer_set 返回。必填参数"
    )


class TimerListInput(BaseModel):
    pass


__all__ = [
    "TimerSetInput",
    "TimerClearInput",
    "TimerListInput",
]
