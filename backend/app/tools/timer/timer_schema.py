# -*- coding: utf-8 -*-
"""
Timer 工具参数 Schema 定义 — 小欧 2026-06-17
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
