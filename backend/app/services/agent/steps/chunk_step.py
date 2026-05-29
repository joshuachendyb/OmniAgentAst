# -*- coding: utf-8 -*-
"""
ChunkStep类 - 流式块步骤

表示LLM生成的流式文本片段：
- type: "chunk"
- is_done() = False → 继续生成

Author: 小沈
Date: 2026-04-15
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
    
    设计依据：补充流式输出统一封装
    """
    
    def __init__(
        self,
        step: int,
        content: str,
        is_reasoning: bool = False,
        timestamp: Optional[int] = None
    ):
        """
        初始化ChunkStep
        
        Args:
            step: 步骤序号
            content: 块内容
            is_reasoning: 是否正在推理
            timestamp: 时间戳（毫秒）
        """
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._content = content
        self._is_reasoning = is_reasoning
    
    def get_type(self) -> str:
        return "chunk"
    
    def get_content(self) -> str:
        return self._content
    
    @property
    def is_reasoning(self) -> bool:
        """获取是否推理中"""
        return self._is_reasoning
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "is_reasoning": self._is_reasoning
        })
        return base_dict
