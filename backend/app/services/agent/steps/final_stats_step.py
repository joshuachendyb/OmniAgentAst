# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════════════════
# final_stats_step.py — FinalStep 的独立统计子类（final_stats 强类型承载）
# ═══════════════════════════════════════════════════════════════════════════════════════
# 编辑历史（最新在底部 §历史）:
# 2026-09-11 北京老陈 定案: final_stats 由 MetaStep 升级为 FinalStatsStep 独立子类
#    —— 因为 "final_stats 要落库 DB 的, 为什么是 Meta 类" 三思结论:
#      MetaStep 语义 = 运行时元事件(start/cancelled/paused 等非终态即时通知, 不落库意义);
#      final_stats 语义 = 终态统计(7 统计键, 落库 chat_task_steps 供历史回放, SSE 延后单发);
#      语义错位 + 门禁需 class 侧强类型化 → 独立子类承载, 与 MetaStep 时代逐键等价(零 backward)。
# 2026-09-11 小欧 TDD 落盘(北京老陈批准): 7 键强类型 + 构造门禁(None/空final_status → ValueError)
#   + to_dict 11 键(4 基类 + 7 统计), 与 agent_telemetry.build_final_stats_step 产出逐键等价。
#
# 【零backward铁律】北京老陈 2026-09-11:
#   step 键语义怪癖(塞 llm_call_count) —— 生产 build_final_stats_step L219 已如此, 前端逐键等价消费;
#   本类【不篡改 step】, 由接线方(telemetry)决定 step 传什么 —— 修=break, 严禁私自改。
#
# Author: 小欧
# Date: 2026-09-11

from typing import Any, Dict, List, Optional

from .base import ReasoningStep


class FinalStatsStep(ReasoningStep):
    """终态统计步骤 —— final_stats 独立强类型子类（非 MetaStep）— 小欧 2026-09-11"""

    TYPE: str = "final_stats"
    IS_DONE: bool = True

    def __init__(
        self,
        step: int,
        *,
        duration: Optional[float] = None,
        artifacts: Optional[List[Any]] = None,
        step_count: Optional[int] = None,
        llm_call_count: Optional[int] = None,
        retry_count: Optional[int] = None,
        tool_stats: Optional[Dict[str, Any]] = None,
        final_status: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        # 【构造门禁】北京老陈 2026-09-11: 7 统计键任一 None / final_status 空串 → ValueError 拒发
        _missing = [
            k
            for k, v in {
                "duration": duration,
                "artifacts": artifacts,
                "step_count": step_count,
                "llm_call_count": llm_call_count,
                "retry_count": retry_count,
                "tool_stats": tool_stats,
                "final_status": final_status,
            }.items()
            if v is None
        ]
        if final_status == "":
            _missing.append("final_status(空串)")
        if _missing:
            raise ValueError(f"FinalStatsStep 门禁: 7 统计键缺/None — {_missing}")
        # 2026-09-11 小欧 TDD红转绿(C11): 【三态枚举门禁】final_status 必须 ∈ {completed, failed, cancelled}
        #   —— 北京老陈 2026-09-11 定案三态; 缺此门禁=前端badge/DB可落非法终值(真实正确性漏洞, 现补)
        if final_status not in {"completed", "failed", "cancelled"}:
            raise ValueError(
                f"FinalStatsStep 门禁: final_status={final_status!r} 非法 — 必须三态 "
                f"(completed/failed/cancelled)"
            )

        ReasoningStep.__init__(self, step, timestamp)
        self._duration = duration
        self._artifacts = list(artifacts) or []
        self._step_count = step_count or 0
        self._llm_call_count = llm_call_count or 0
        self._retry_count = retry_count or 0
        self._tool_stats = dict(tool_stats) or {}
        self._final_status = final_status

    # ── 7 统计键只读 property —— 强类型读取口（前端/落库/SSE 统一走 to_dict）— 小欧 2026-09-11 ──
    @property
    def duration(self) -> float:
        return self._duration

    @property
    def artifacts(self) -> List[Any]:
        return self._artifacts

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def llm_call_count(self) -> int:
        return self._llm_call_count

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def tool_stats(self) -> Dict[str, Any]:
        return self._tool_stats

    @property
    def final_status(self) -> str:
        return self._final_status

    def get_content(self) -> str:
        """终态统计帧无正文 —— 对齐 MetaStep 时代 content="" 契约 — 小欧 2026-09-11"""
        return ""

    def _extra_fields(self) -> Dict[str, Any]:
        """7 统计键输出 —— to_dict 11 键 = 4 基类(type/step/timestamp/content) + 7 统计 — 小欧 2026-09-11
        ★ 键名与 MetaStep 时代 build_final_stats_step 产物逐键等价(LL219 怪癖除外: step 由基类承载, 接线方定)
        ★ step 键语义沿用生产接线(telemetry L219 塞 llm_call_count)—— 本类不篡改、修=break — 北京老陈 2026-09-11
        """
        return {
            "duration": self._duration,
            "artifacts": list(self._artifacts) or [],
            "step_count": self._step_count or 0,
            "llm_call_count": self._llm_call_count or 0,
            "retry_count": self._retry_count or 0,
            "tool_stats": dict(self._tool_stats) or {},
            "final_status": self._final_status,
        }
