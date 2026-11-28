# -*- coding: utf-8 -*-
"""
delegateagent_schema — delegateagent 工具参数模型
小欧 2026-11-27
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DelegateAgentInput(BaseModel):
    """delegateagent 工具入参 — LLM 侧看到的参数结构"""
    agent_id: str = Field(
        ...,
        description="目标子Agent ID（取值见工具描述里动态列出的可用列表）"
    )
    task: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="委托给子Agent的任务描述（自包含，含必要背景，≤500字）"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="附加上下文（文件路径/数据片段/约束条件等，按需传入）"
    )
    wait: bool = Field(
        True,
        description="是否同步等待结果（True=本轮直接返回摘要+用量，P0 已实现；False=立即返回 delegate_id，后台跑完自动回灌，P1）"
    )
