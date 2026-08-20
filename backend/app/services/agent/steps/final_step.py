
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
# 2026-08-20 - 小欧 - 11.1 token 四层同构: FinalStep 新增 task/session/chain_accumulated_tokens 三参数+三@property+_extra_fields 三键输出, 承载四层 token 累计透传至前端

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
        task_accumulated_tokens: Optional[Dict[str, int]] = None,    # 11.1 新增 — 小欧 2026-08-20
        session_accumulated_tokens: Optional[Dict[str, int]] = None, # 11.1 新增
        chain_accumulated_tokens: Optional[Dict[str, int]] = None,   # 11.1 新增（计算派生，不落库）
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
        self._task_accumulated_tokens = task_accumulated_tokens       # 11.1 新增
        self._session_accumulated_tokens = session_accumulated_tokens # 11.1 新增
        self._chain_accumulated_tokens = chain_accumulated_tokens     # 11.1 新增
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

    @property
    def task_accumulated_tokens(self) -> Optional[Dict[str, int]]:  # 11.1 新增 — 小欧 2026-08-20
        return self._task_accumulated_tokens

    @property
    def session_accumulated_tokens(self) -> Optional[Dict[str, int]]:  # 11.1 新增
        return self._session_accumulated_tokens

    @property
    def chain_accumulated_tokens(self) -> Optional[Dict[str, int]]:  # 11.1 新增
        return self._chain_accumulated_tokens

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "response": self._response,
            "outcome": self._outcome,
            "error_type": self._error_type,
            "error_message": self._error_message,
            "model": self._model,
            "provider": self._provider,
            "accumulated_usage": self._accumulated_usage,
            "task_accumulated_tokens": self._task_accumulated_tokens,       # 11.1 新增
            "session_accumulated_tokens": self._session_accumulated_tokens, # 11.1 新增
            "chain_accumulated_tokens": self._chain_accumulated_tokens,     # 11.1 新增
            "reasoning": self._reasoning,
        }
