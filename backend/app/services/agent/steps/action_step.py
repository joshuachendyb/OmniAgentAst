# -*- coding: utf-8 -*-
"""
ActionToolStep类 - 工具执行步骤

表示工具执行的结果：
- type: "action_tool"
- is_done() = False → 不结束，继续生成observation

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional

from .base import ReasoningStep, ToolMixin


class ActionToolStep(ToolMixin, ReasoningStep):
    """
    ActionToolStep类 - 工具执行步骤
    
    表示工具执行的结果：
    - type: "action_tool"
    - is_done() = False → 不结束，继续生成observation
    
    字段说明：
    - execution_status: 执行状态（success/error/warning）
    - summary: 执行摘要
    - execution_result: 执行结果数据（原raw_data）
    - error_message: 错误信息（成功时为空字符串）
    - action_retry_count: 重试次数（原retry_count）
    - execution_time_ms: 执行耗时（毫秒）
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        execution_status: str = "success",
        summary: str = "",
        execution_result: Any = None,
        error_message: str = "",
        action_retry_count: int = 0,
        execution_time_ms: int = 0,
        timestamp: Optional[int] = None
    ):
        """
        初始化ActionToolStep
        
        职责：只传递执行结果摘要（status/data/耗时/重试），
        详细信息（code/warning/next_actions/attachment）由ObservationStep负责。
        
        Args:
            step: 步骤序号
            tool_name: 工具名称
            tool_params: 工具参数
            execution_status: 执行状态（success/error/warning）
            summary: 执行摘要
            execution_result: 执行结果数据（原raw_data）
            error_message: 错误信息（成功时为空）
            action_retry_count: 重试次数（原retry_count）
            execution_time_ms: 执行耗时（毫秒）
            timestamp: 时间戳（毫秒）
        """
        # 调用ToolMixin初始化
        ToolMixin.__init__(self, tool_name, tool_params)
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._execution_status = execution_status
        self._summary = summary
        self._execution_result = execution_result
        self._error_message = error_message
        self._action_retry_count = action_retry_count
        self._execution_time_ms = execution_time_ms
    
    def get_type(self) -> str:
        return "action_tool"
    
    def get_content(self) -> str:
        return self._summary or self._error_message
    
    @property
    def execution_status(self) -> str:
        """获取执行状态"""
        return self._execution_status
    
    @property
    def summary(self) -> str:
        """获取执行摘要"""
        return self._summary
    
    @property
    def execution_result(self) -> Any:
        """获取执行结果数据"""
        return self._execution_result
    
    @property
    def error_message(self) -> str:
        """获取错误信息"""
        return self._error_message
    
    @property
    def action_retry_count(self) -> int:
        """获取重试次数"""
        return self._action_retry_count
    
    @property
    def execution_time_ms(self) -> int:
        """获取执行耗时"""
        return self._execution_time_ms
    
    @property
    def is_error(self) -> bool:
        """是否执行失败"""
        return self._execution_status == "error"
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "execution_status": self._execution_status,
            "execution_result": self._execution_result,
            "raw_data": self._execution_result,
            "action_retry_count": self._action_retry_count,
            "execution_time_ms": self._execution_time_ms,
            "tool_name": self._tool_name,
            "tool_params": self._tool_params,
        })
        return base_dict
