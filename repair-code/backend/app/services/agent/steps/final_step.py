
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原FinalStep仅承载成功终态(completed), 失败/取消用ErrorStep/MetaStep单独表示,
#          导致response_text仅由final事件填充, 失败终态无FinalStep→body为空(unit-09暴露);
#          且前端需同时处理final/error/cancelled三种type, 逻辑分散易遗漏。
#   【思路】FinalStep多态化: 新增outcome/error_type/error_message三字段,
#          失败→FinalStep(outcome="failed"), 取消→FinalStep(outcome="cancelled"),
#          成功→FinalStep(outcome="completed"); 终态统一由type=final承载,
#          前端仅需按outcome分流, 消除三种type的分散处理。
#   【改法】①__init__新增outcome/error_type/error_message参数(默认值向后兼容)
#          ②新增三个@property读取器 ③_extra_fields()输出这三个字段
#          ④TYPE="final"不变, IS_DONE=True不变, 向后兼容旧数据。
# 2026-07-18 小欧 #26 fix: outcome参数Literal["completed","failed","cancelled"]约束
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
# 2026-07-22 小欧 - 新增 accumulated_usage 可选字段(累计消耗统计), _extra_fields 输出供前端显示

from typing import Any, Dict, Literal, Optional

from .base import ReasoningStep


class FinalStep(ReasoningStep):
    """最终回答步骤 - Agent完成,最终给出答案

    2026-07-18 小欧 多态自包含终态重构:
    outcome字段声明终态结果: completed(成功)/failed(失败)/cancelled(取消)
    error_type/error_message在失败时承载错误详情, 成功/取消时为空。
    """

    TYPE: str = "final"
    IS_DONE: bool = True

    def __init__(
        self,
        step: int,
        response: str,
        thought: str = "",
        outcome: Literal["completed", "failed", "cancelled"] = "completed",  # #26 fix: Literal约束 — 小欧 2026-07-18
        error_type: str = "",  # 小欧 2026-07-18: 失败时的错误类型(如llm_error/agent_operation_error)
        error_message: str = "",  # 小欧 2026-07-18: 失败/取消时的错误信息
        model: Optional[str] = None,
        provider: Optional[str] = None,
        is_finished: bool = True,
        display_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        accumulated_usage: Optional[Dict[str, int]] = None,  # 2026-07-22 - 小欧 - 累计消耗: prompt_tokens/completion_tokens/total_tokens
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._response = response
        self._thought = thought
        self._outcome = outcome
        self._error_type = error_type
        self._error_message = error_message
        self._model = model
        self._provider = provider
        self._is_finished = is_finished
        self._display_name = display_name or (f"{provider} ({model})" if provider and model else provider or model or "")
        self._accumulated_usage = accumulated_usage  # 2026-07-22 - 小欧

    def get_content(self) -> str:
        return self._response

    @property
    def response(self) -> str:
        return self._response

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def outcome(self) -> str:  # 小欧 2026-07-18: 终态声明读取器
        return self._outcome

    @property
    def error_type(self) -> str:  # 小欧 2026-07-18: 错误类型读取器
        return self._error_type

    @property
    def error_message(self) -> str:  # 小欧 2026-07-18: 错误信息读取器
        return self._error_message

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    @property
    def display_name(self) -> str:
        return self._display_name

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "response": self._response,
            "thought": self._thought,
            "outcome": self._outcome,  # 小欧 2026-07-18: 输出终态声明
            "error_type": self._error_type,  # 小欧 2026-07-18: 输出错误类型
            "error_message": self._error_message,  # 小欧 2026-07-18: 输出错误信息
            "model": self._model,
            "provider": self._provider,
            "is_finished": self._is_finished,
            "display_name": self._display_name,
            "accumulated_usage": self._accumulated_usage,  # 2026-07-22 - 小欧
        }

