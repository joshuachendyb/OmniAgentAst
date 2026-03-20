# -*- coding: utf-8 -*-
"""
ReAct 步骤类型定义

Author: 小沈 - 2026-03-21
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


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
    """ReAct步骤（兼容旧版本）"""
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "timestamp": self.timestamp.isoformat()
        }
