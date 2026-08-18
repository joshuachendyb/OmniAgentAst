
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
# 2026-08-18 小欧 - §10.3.3(4): 删 thought/is_finished/display_name(冗余); 新增 reasoning(历史回放推理载体)

from typing import Any, Dict, Literal, Optional

from .base import ReasoningStep


class FinalStep(ReasoningStep):
    """最终回答步骤 - 多态自包含终态（§10.3.3(4）"""

    TYPE: str = "final"
    IS_DONE: bool = True

    def __init__(
        self,
        step: int,
        response: str = "",
        outcome: Literal["completed", "failed", "cancelled"] = "completed",
        error_type: str = "",
        error_message: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        accumulated_usage: Optional[Dict[str, int]] = None,
        reasoning: str = "",
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._response = response
        self._outcome = outcome
        self._error_type = error_type
        self._error_message = error_message
        self._model = model
        self._provider = provider
        self._accumulated_usage = accumulated_usage
        self._reasoning = reasoning

    def get_content(self) -> str:
        return self._response

    @property
    def response(self) -> str:
        return self._response

    @property
    def outcome(self) -> str:
        return self._outcome

    @property
    def error_type(self) -> str:
        return self._error_type

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def reasoning(self) -> str:
        return self._reasoning

    @property
    def accumulated_usage(self) -> Optional[Dict[str, int]]:
        return self._accumulated_usage

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "response": self._response,
            "outcome": self._outcome,
            "error_type": self._error_type,
            "error_message": self._error_message,
            "model": self._model,
            "provider": self._provider,
            "accumulated_usage": self._accumulated_usage,
            "reasoning": self._reasoning,
        }
