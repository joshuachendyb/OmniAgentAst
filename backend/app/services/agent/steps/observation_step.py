# -*- coding: utf-8 -*-
"""
ObservationStep类 - 观察步骤

表示工具执行后的观察结果:
- type: "observation"
- is_done() = return_direct → 根据工具是否要求直接返回

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional, List

from .base import ReasoningStep


class ObservationStep(ReasoningStep):
    """
    ObservationStep类 - 观察步骤
    
    表示工具执行后的观察结果:
    - type: "observation"
    - is_done() = return_direct → 根据工具是否要求直接返回
    
    字段说明:
    - observation: 观察结果
    - return_direct: 是否直接返回(工具要求直接返回结果)
    
    设计依据:13.2.2.2节具体实现类设计
    """

    TYPE: str = "observation"
    
    def __init__(
        self,
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        observation: str = "",
        return_direct: bool = False,
        execution_status: str = "",
        code: str = "",
        warning: Optional[str] = None,
        attachment: Any = None,
        next_actions: Optional[List[Dict[str, str]]] = None,
        summary: str = "",
        error_message: str = "",
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        
        self._tool_name = tool_name
        self._tool_params = tool_params
        self._observation = observation
        self._return_direct = return_direct
        self._execution_status = execution_status
        self._code = code
        self._warning = warning
        self._attachment = attachment
        self._next_actions = next_actions
        self._summary = summary
        self._error_message = error_message
    
    def get_content(self) -> str:
        return self._observation
    
    @property
    def observation(self) -> str:
        return self._observation
    
    @property
    def return_direct(self) -> bool:
        return self._return_direct
    
    @property
    def summary(self) -> str:
        return self._summary
    
    @property
    def error_message(self) -> str:
        return self._error_message
    
    def is_done(self) -> bool:
        return self._return_direct

    def _build_observation_obj(self) -> Dict[str, Any]:
        summary_text = self._observation or self._summary or self._error_message or "执行完成"
        obj = {
            "summary": summary_text,
            "tool_name": self._tool_name or "unknown",
            "tool_params": self._tool_params or {},
            "return_direct": self._return_direct or False,
        }
        if self._execution_status:
            obj["execution_status"] = self._execution_status
        if self._error_message:
            obj["error_message"] = self._error_message
        if self._warning:
            obj["warning"] = self._warning
        if self._next_actions:
            obj["next_actions"] = self._next_actions
        if self._attachment is not None:
            obj["attachment"] = self._attachment
        return obj

    def _extra_fields(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"observation": self._build_observation_obj()}
        if self._code:
            d["code"] = self._code
        return d
