# -*- coding: utf-8 -*-
"""
ChunkStep类 - 流式块步骤

表示LLM生成的流式文本片段：
- type: "chunk"
- is_done() = False → 继续生成

Author: 小沈
Date: 2026-04-15
Updated: 2026-05-30 新增 thought/reasoning/_thinking/model/provider 字段
"""

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ChunkStep(ReasoningStep):
    """
    ChunkStep类 - 流式块步骤
    
    表示LLM生成的流式文本片段：
    - type: "chunk"
    - is_done() = False → 继续生成
    
    字段说明：
    - content: 块内容
    - is_reasoning: 是否正在推理
    - thought: 思考内容
    - reasoning: 推理过程
    - _thinking: 内部思考标记
    - model: 模型名称
    - provider: 提供商
    """
    
    def __init__(
        self,
        step: int,
        content: str,
        is_reasoning: bool = False,
        thought: str = '',
        reasoning: str = '',
        thinking: str = '',
        model: str = '',
        provider: str = '',
        timestamp: Optional[int] = None
    ):
        """
        初始化ChunkStep
        
        Args:
            step: 步骤序号
            content: 块内容
            is_reasoning: 是否正在推理
            thought: 思考内容
            reasoning: 推理过程
            thinking: 内部思考标记
            model: 模型名称
            provider: 提供商
            timestamp: 时间戳（毫秒）
        """
        ReasoningStep.__init__(self, step, timestamp)
        
        self._content = content
        self._is_reasoning = is_reasoning
        self._thought = thought
        self._reasoning = reasoning
        self._thinking = thinking
        self._model = model
        self._provider = provider
    
    def get_type(self) -> str:
        return "chunk"
    
    def get_content(self) -> str:
        return self._content
    
    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning
    
    @property
    def thought(self) -> str:
        return self._thought
    
    @property
    def reasoning(self) -> str:
        return self._reasoning
    
    @property
    def thinking(self) -> str:
        return self._thinking
    
    @property
    def model(self) -> str:
        return self._model
    
    @property
    def provider(self) -> str:
        return self._provider
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "is_reasoning": self._is_reasoning,
            "thought": self._thought,
            "reasoning": self._reasoning,
            "_thinking": self._thinking,
            "model": self._model,
            "provider": self._provider,
        })
        return base_dict
