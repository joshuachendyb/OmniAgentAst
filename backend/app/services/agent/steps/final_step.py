# -*- coding: utf-8 -*-
"""
FinalStep类 - 最终回答步骤

表示Agent完成，最终给出答案：
- type: "final"
- is_done() = True → 结束循环

Author: 小沈
Date: 2026-04-15
Updated: 2026-05-30 新增 is_finished/is_streaming/is_reasoning/display_name 字段
"""

from typing import Any, Dict, Optional

from .base import ReasoningStep


class FinalStep(ReasoningStep):
    """
    FinalStep类 - 最终回答步骤
    
    表示Agent完成，最终给出答案：
    - type: "final"
    - is_done() = True → 结束循环
    
    字段说明：
    - response: 最终回答
    - thought: 思考过程
    - model: 模型名称
    - provider: 提供商
    - is_finished: 业务完成标志
    - is_streaming: 是否流式输出
    - is_reasoning: 是否在推理中
    - display_name: 模型显示名称
    """
    
    def __init__(
        self,
        step: int,
        response: str,
        thought: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        is_finished: bool = True,
        is_streaming: bool = False,
        is_reasoning: bool = False,
        display_name: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        """
        初始化FinalStep
        
        Args:
            step: 步骤序号
            response: 最终回答
            thought: 思考过程
            model: 模型名称（可选）
            provider: 提供商（可选）
            is_finished: 业务完成标志
            is_streaming: 是否流式输出
            is_reasoning: 是否在推理中
            display_name: 模型显示名称（可选）
            timestamp: 时间戳（毫秒）
        """
        ReasoningStep.__init__(self, step, timestamp)
        
        self._response = response
        self._thought = thought
        self._model = model
        self._provider = provider
        self._is_finished = is_finished
        self._is_streaming = is_streaming
        self._is_reasoning = is_reasoning
        self._display_name = display_name or (f"{provider} ({model})" if provider and model else provider or model or "")
    
    def get_type(self) -> str:
        return "final"
    
    def get_content(self) -> str:
        return self._response
    
    @property
    def response(self) -> str:
        return self._response
    
    @property
    def thought(self) -> str:
        return self._thought
    
    @property
    def model(self) -> Optional[str]:
        return self._model
    
    @property
    def provider(self) -> Optional[str]:
        return self._provider
    
    @property
    def is_finished(self) -> bool:
        return self._is_finished
    
    @property
    def is_streaming(self) -> bool:
        return self._is_streaming
    
    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning
    
    @property
    def display_name(self) -> str:
        return self._display_name
    
    def is_done(self) -> bool:
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "response": self._response,
            "thought": self._thought,
            "model": self._model,
            "provider": self._provider,
            "is_finished": self._is_finished,
            "is_streaming": self._is_streaming,
            "is_reasoning": self._is_reasoning,
            "display_name": self._display_name,
        })
        return base_dict
