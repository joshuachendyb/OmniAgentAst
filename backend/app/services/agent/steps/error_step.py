# -*- coding: utf-8 -*-
"""
ErrorStep类 - 错误步骤

表示执行过程中出现错误:
- type: "error"
- is_done() = True → 结束循环

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ErrorStep(ReasoningStep):
    """
    ErrorStep类 - 错误步骤
    
    表示执行过程中出现错误:
    - type: "error"
    - is_done() = True → 结束循环
    
    字段说明:
    - error_type: 错误类型
    - error_message: 错误信息
    - recoverable: 是否可恢复
    
    设计依据:13.2.2.2节具体实现类设计
    """

    TYPE: str = "error"
    IS_DONE: bool = True
    
    def __init__(
        self,
        step: int,
        error_type: str,
        error_message: str,
        recoverable: bool = False,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        reasoning: str = "",
        is_reasoning: bool = False,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        details: Optional[str] = None,
        stack: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        """
        初始化ErrorStep
        
        Args:
            step: 步骤序号
            error_type: 错误类型
            error_message: 错误信息
            recoverable: 是否可恢复
            model: 模型名称(可选)
            provider: 提供商(可选)
            reasoning: 思考过程(可选)
            is_reasoning: 是否推理中(可选)
            context: 错误上下文(可选)
            retry_after: 重试等待秒数(可选)
            details: 详细错误信息(可选)
            stack: 堆栈信息(可选)
            timestamp: 时间戳(毫秒)
        """
        ReasoningStep.__init__(self, step, timestamp)
        
        self._error_type = error_type
        self._error_message = error_message
        self._recoverable = recoverable
        self._model = model
        self._provider = provider
        self._reasoning = reasoning
        self._is_reasoning = is_reasoning
        self._context = context
        self._retry_after = retry_after
        self._details = details
        self._stack = stack
    
    def get_content(self) -> str:
        return self._error_message
    
    @property
    def error_type(self) -> str:
        return self._error_type
    
    @property
    def error_message(self) -> str:
        return self._error_message
    
    @property
    def recoverable(self) -> bool:
        return self._recoverable
    
    @property
    def model(self) -> Optional[str]:
        return self._model
    
    @property
    def provider(self) -> Optional[str]:
        return self._provider
    
    @property
    def reasoning(self) -> str:
        return self._reasoning
    
    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning
    
    @property
    def context(self) -> Optional[Dict[str, Any]]:
        return self._context
    
    @property
    def retry_after(self) -> Optional[int]:
        return self._retry_after
    
    @property
    def details(self) -> Optional[str]:
        return self._details
    
    @property
    def stack(self) -> Optional[str]:
        return self._stack
    
    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "error_type": self._error_type,
            "error_message": self._error_message,
            "recoverable": self._recoverable,
            "model": self._model,
            "provider": self._provider,
            "reasoning": self._reasoning,
            "is_reasoning": self._is_reasoning,
            "context": self._context,
            "retry_after": self._retry_after,
            "details": self._details,
            "stack": self._stack,
        }
