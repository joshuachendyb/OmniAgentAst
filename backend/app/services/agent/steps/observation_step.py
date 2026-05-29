# -*- coding: utf-8 -*-
"""
ObservationStep类 - 观察步骤

表示工具执行后的观察结果：
- type: "observation"
- is_done() = return_direct → 根据工具是否要求直接返回

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional, List

from .base import ReasoningStep, ToolMixin


class ObservationStep(ToolMixin, ReasoningStep):
    """
    ObservationStep类 - 观察步骤
    
    表示工具执行后的观察结果：
    - type: "observation"
    - is_done() = return_direct → 根据工具是否要求直接返回
    
    字段说明：
    - observation: 观察结果
    - return_direct: 是否直接返回（工具要求直接返回结果）
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
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
        """
        初始化ObservationStep
        
        职责：传递执行详细信息（code/warning/next_actions/attachment/summary/error_message），
        业务数据（data）由ActionToolStep负责，不重复。
        
        Args:
            step: 步骤序号
            tool_name: 工具名称
            tool_params: 工具参数
            observation: 观察结果文本（summary）
            return_direct: 是否直接返回
            execution_status: 执行状态
            code: 原始错误码
            warning: 警告文本
            attachment: 二进制附件
            next_actions: 推荐下一步操作
            summary: 执行摘要（给前端展示用）
            error_message: 错误信息（给前端展示用）
            timestamp: 时间戳（毫秒）
        """
        ToolMixin.__init__(self, tool_name, tool_params)
        ReasoningStep.__init__(self, step, timestamp)
        
        self._observation = observation
        self._return_direct = return_direct
        self._execution_status = execution_status
        self._code = code
        self._warning = warning
        self._attachment = attachment
        self._next_actions = next_actions
        self._summary = summary
        self._error_message = error_message
    
    def get_type(self) -> str:
        return "observation"
    
    def get_content(self) -> str:
        return self._observation
    
    @property
    def observation(self) -> str:
        """获取观察结果"""
        return self._observation
    
    @property
    def return_direct(self) -> bool:
        """获取是否直接返回"""
        return self._return_direct
    
    @property
    def summary(self) -> str:
        """获取执行摘要"""
        return self._summary
    
    @property
    def error_message(self) -> str:
        """获取错误信息"""
        return self._error_message
    
    def is_done(self) -> bool:
        return self._return_direct
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        
        # 【改造 2026-05-22 小沈】observation改为JSON对象，符合第13章设计方案
        # 【修复 2026-05-22 小资】summary为空时使用error_message或默认值，避免前端渲染失败
        summary_text = self._observation or self._summary or self._error_message or "执行完成"
        observation_obj = {
            "summary": summary_text,
            "tool_name": self._tool_name or "unknown",
            "tool_params": self._tool_params or {},
            "return_direct": self._return_direct or False,
        }
        
        if self._execution_status:
            observation_obj["execution_status"] = self._execution_status
        if self._error_message:
            observation_obj["error_message"] = self._error_message
        if self._warning:
            observation_obj["warning"] = self._warning
        if self._next_actions:
            observation_obj["next_actions"] = self._next_actions
        if self._attachment is not None:
            observation_obj["attachment"] = self._attachment
        
        d = {"observation": observation_obj}
        if self._code:
            d["code"] = self._code
        
        base_dict.update(d)
        return base_dict
