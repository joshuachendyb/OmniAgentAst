# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

按SRP原则拆分,每个文件单一职责:
- base.py: ReasoningStep(ABC) + MetaStep (start/cancelled/paused/resumed/retrying/authorization_required)
- action_step.py: ActionStep (action模式)
- observation_step.py: ObservationStep (observation模式)
- chunk_step.py: ChunkStep
- thought_step.py: ThoughtStep (仅落库)
- thought_start_step.py: ThoughtStartStep (仅SSE实时信号)
- start_content_step.py: StartStep (start完整任务契约, 落库, content=context_summary)
- final_step.py: FinalStep
- error_step.py: ErrorStep
- final_stats_step.py: FinalStatsStep (final_stats终态统计)

Author: 小沈
Date: 2026-04-15
Updated: 2026-06-22 SRP拆分：ActionStep(action_tool) + ObservationStep(observation)
Updated: 2026-08-18 小欧 - §10.3: 废action_tool改action, 新增ThoughtStartStep, ObservationStep仅tool_result, FinalStep删冗余加reasoning
Updated: 2026-09-11 小欧 - 接线①: 导出 FinalStatsStep 子类(打字法显式写成 [27] 定案的 final_stats 终态) — 小欧 2026-09-11
"""
from .base import ReasoningStep, MetaStep
from .action_step import ActionStep
from .observation_step import ObservationStep
from .chunk_step import ChunkStep
from .thought_step import ThoughtStep
from .thought_start_step import ThoughtStartStep   # 2026-08-18 小欧 新增
from .start_content_step import StartStep           # 2026-08-18 小欧 新增(§10.1.2 P7 start 拆双)
from .final_step import FinalStep
from .error_step import ErrorStep
from .final_stats_step import FinalStatsStep

__all__ = [
    "ReasoningStep",
    "MetaStep",
    "ActionStep",
    "ObservationStep",
    "ChunkStep",
    "ThoughtStep",
    "ThoughtStartStep",
    "StartStep",
    "FinalStep",
    "ErrorStep",
    "FinalStatsStep",
]

# ============================================================
# 全部事件类型登记源(唯一登记处) — 小欧-2026-09-12
# 纪律([29]4C通道路由缺口核查报告-小欧-2026-09-12 §7.3.1): 新增任何 Step/事件类型必须先在此登记,
#   并携带通道路由表(SSE/DB/短信号 三列)逐行对照迁移, 缺一不放行。
# 转发表推导: stream_orchestrator._SSE_FORWARD_TYPES = ALL_STEP_TYPES − {"thought"}(仅落库集), DRY 单一来源。
# 全集来源: [29]§7.1.3(当前 HEAD 4bf3ea987 逐字面值实证)。
ALL_STEP_TYPES = frozenset({
    # SSE + 落库(SSE✓/DB✓)
    "start", "action", "observation", "final", "final_stats",
    # 仅SSE(SSE✓/DB✗, 实时信号)
    "chunk", "thought-start",
    "error", "usage", "paused", "resumed", "retrying",
    "user_rejected", "stats", "context_overview", "truncated",
    # 仅落库(SSE✗/DB✓)
    "thought",
    # 防御性保留(当前无独立发射源)
    "cancelled",
})

