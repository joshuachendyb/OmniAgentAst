# -*- coding: utf-8 -*-
"""
ReAct 步骤类型定义

Author: 小沈 - 2026-03-21

【修改 2026-03-31】
- Step.timestamp 改为 int 类型，存储毫秒时间戳
- to_dict() 返回毫秒时间戳，而非 isoformat()
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from app.chat_stream.chat_helpers import create_timestamp


@dataclass
class ThoughtStep:
    """Thought阶段的数据结构"""
    step_number: int
    content: str
    reasoning: Optional[str] = None
    action_tool: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "content": self.content,
            "reasoning": self.reasoning,
            "action_tool": self.action_tool,
            "params": self.params
        }


@dataclass
class ActionToolStep:
    """Action阶段的数据结构"""
    step_number: int
    tool_name: str
    tool_params: Dict[str, Any] = field(default_factory=dict)
    execution_status: str = "success"
    summary: str = ""
    raw_data: Optional[Dict[str, Any]] = None
    action_retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "execution_status": self.execution_status,
            "summary": self.summary,
            "raw_data": self.raw_data,
            "action_retry_count": self.action_retry_count
        }


@dataclass
class ObservationStep:
    """Observation阶段的数据结构"""
    step_number: int
    execution_status: str
    summary: str
    raw_data: Optional[Dict[str, Any]] = None
    content: str = ""
    reasoning: Optional[str] = None
    action_tool: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    is_finished: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "execution_status": self.execution_status,
            "summary": self.summary,
            "raw_data": self.raw_data,
            "content": self.content,
            "reasoning": self.reasoning,
            "action_tool": self.action_tool,
            "params": self.params,
            "is_finished": self.is_finished
        }


@dataclass
class Step:
    """ReAct步骤（兼容旧版本）【修改 2026-03-31】timestamp改为毫秒int类型"""
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Optional[Dict[str, Any]] = None
    # 【修改 2026-03-31】从 datetime 改为 int，使用毫秒时间戳
    timestamp: int = field(default_factory=create_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            # 【修改 2026-03-31】直接返回毫秒时间戳，不再转换
            "timestamp": self.timestamp
        }
