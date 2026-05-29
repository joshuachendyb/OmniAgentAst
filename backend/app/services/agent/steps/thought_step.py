# -*- coding: utf-8 -*-
"""
ThoughtStep类 - 思考步骤

对应LLM的Thought输出，表示正在思考并准备执行工具：
- type: "thought"
- is_done() = False → 不结束，继续执行工具

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional

from .base import ReasoningStep, ToolMixin


class ThoughtStep(ToolMixin, ReasoningStep):
    """
    ThoughtStep类 - 思考步骤
    
    对应LLM的Thought输出，表示正在思考并准备执行工具：
    - type: "thought"
    - is_done() = False → 不结束，继续执行工具
    
    字段说明：
    - content: 思考内容摘要（用户可见）
    - thought: 详细思考内容
    - reasoning: 推理过程
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
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
        """
        初始化ThoughtStep
        
        Args:
            step: 步骤序号
            content: 思考内容摘要（用户可见）
            tool_name: 工具名称
            tool_params: 工具参数
            thought: 详细思考内容
            reasoning: 推理过程
            timestamp: 时间戳（毫秒）
        """
        # 调用ToolMixin初始化
        ToolMixin.__init__(self, tool_name, tool_params)
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._content = content
        self._thought = thought or content
        self._reasoning = reasoning
    
    def get_type(self) -> str:
        return "thought"
    
    def get_content(self) -> str:
        return self._content
    
    @property
    def content(self) -> str:
        """获取思考内容摘要"""
        return self._content
    
    @property
    def thought(self) -> str:
        """获取详细思考内容"""
        return self._thought
    
    @property
    def reasoning(self) -> str:
        """获取推理过程"""
        return self._reasoning
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "thought": self._thought,
            "reasoning": self._reasoning,
            "tool_name": self._tool_name,  # 来自ToolMixin
            "tool_params": self._tool_params,  # 来自ToolMixin
        })
        return base_dict
