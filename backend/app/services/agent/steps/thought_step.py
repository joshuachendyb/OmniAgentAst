# -*- coding: utf-8 -*-
"""
ThoughtStep类 - 思考步骤

对应LLM的Thought输出,表示正在思考并准备执行工具:
- type: "thought"
- is_done() = False → 不结束,继续执行工具

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ThoughtStep(ReasoningStep):
    """
    ThoughtStep类 - 思考步骤
    
    对应LLM的Thought输出,表示正在思考并准备执行工具:
    - type: "thought"
    - is_done() = False → 不结束,继续执行工具
    
    字段说明:
    - content: 思考内容摘要(用户可见)
    - thought: 详细思考内容
    - reasoning: 推理过程
    
    设计依据:13.2.2.2节具体实现类设计
    """

    TYPE: str = "thought"
    
    def __init__(
        self,
        step: int,
        content: str,
        tool_name: str = "",
        tool_params: Dict[str, Any] = None,
        thought: str = "",
        reasoning: str = "",
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        
        self._content = content
        self._thought = thought or content
        self._reasoning = reasoning
        self._tool_name = tool_name
        self._tool_params = tool_params or {}
    
    def get_content(self) -> str:
        return self._content
    
    @property
    def content(self) -> str:
        return self._content
    
    @property
    def thought(self) -> str:
        return self._thought
    
    @property
    def reasoning(self) -> str:
        return self._reasoning
    
    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "thought": self._thought,
            "reasoning": self._reasoning,
            "tool_name": self._tool_name,
            "tool_params": self._tool_params,
        }
