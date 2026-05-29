# -*- coding: utf-8 -*-
"""
FinalStep类 - 最终回答步骤

表示Agent完成，最终给出答案：
- type: "final"
- is_done() = True → 结束循环

Author: 小沈
Date: 2026-04-15
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
    - is_finished: 业务完成标志
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        response: str,
        thought: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
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
            timestamp: 时间戳（毫秒）
            
        说明【2026-05-04 小沈】：
        - 不需要 is_finished: type="final" 本身就是已完成标识
        - 不需要 is_streaming: 最终回答不是流式，流式用SHE实时推送
        - 不需要 is_reasoning: type="final" 不可能在推理中
        """
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._response = response
        self._thought = thought
        self._model = model
        self._provider = provider
    
    def get_type(self) -> str:
        return "final"
    
    def get_content(self) -> str:
        return self._response
    
    @property
    def response(self) -> str:
        """获取最终回答"""
        return self._response
    
    @property
    def thought(self) -> str:
        """获取思考过程"""
        return self._thought
    
    @property
    def model(self) -> Optional[str]:
        """获取模型名称"""
        return self._model
    
    @property
    def provider(self) -> Optional[str]:
        """获取提供商"""
        return self._provider
    
    def is_done(self) -> bool:
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "response": self._response,
            "thought": self._thought,
            "model": self._model,
            "provider": self._provider,
        })
        return base_dict
