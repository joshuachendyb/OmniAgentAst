# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-29 小欧 新建: 输入框引用阈值单一真源(从 DTO/resolver/budget/前端散落收口) — 小欧-2026-10-29
"""services.refs.limits — 引用预算阈值的唯一真源

职责(单一职责): 由「本次生效模型的 context_limit」派生出引用链路需要的全部阈值:
  单条上限/合计上限/拒绝线(首发) + 插话上限(interject) + 字符上限 + MAX_REFS。
为何独立: 阈值散在 DTO/resolver/budget/前端四处的历史已实测分叉(2MB 在 models.py:19 与
  browse_service.py:112 两处独立取值, 口径已分家); 本模块成为唯一入口, 改阈值只改一处。
不读盘、不裁内容: 纯计算; 磁盘读取与内容降级归 resolver/budget, 职责边界不越。
"""
from dataclasses import dataclass

from app.config import get_config
from app.services.agent.compaction_constants import (
    CHARS_PER_TOKEN, COMPACTION_BUFFER, TOOLS_TOKEN_RESERVE,
)

# 引用条数上限: 前端入队即拦、后端 DTO 再拦(双保险, 防止任意条引用直入 prompt)
MAX_REFS = 20


@dataclass(frozen=True)
class RefLimits:
    """一批阈值(预算基准派生)。全部只读, 供 resolver/budget/orchestrator 消费。"""
    budget_base: int          # 预算基准 = context_limit - compaction_buffer - tools_token_reserve
    single_cap_tokens: int    # 首发单条上限(预算×0.20)
    total_cap_tokens: int     # 首发合计上限(预算×0.40)
    reject_tokens: int        # 首发拒绝线(预算×0.60)
    interject_cap_tokens: int # 插话单条与合计同值(预算×0.05)
    single_cap_chars: int     # 单条字符上限(= 单条上限×CHARS_PER_TOKEN)
    read_max_bytes: int       # 单条读取字节上限(= 单条字符上限, 保守 1 字符 1 字节)


def budget_base_of(context_limit: int) -> int:
    """预算基准: 窗口 - 输出缓冲 - tools预留。与 trim_history 同源口径(message_builder.py:531)。

    2026-10-29 小欧 - 运行时化: context_limit 由 agent_runner.py:627 用 llm_service.context_limit
    覆盖 MAX_CONTEXT_TOKENS, 故本函数必须接收运行时值, 禁写死 262144/212144。
    """
    return int(context_limit) - COMPACTION_BUFFER - TOOLS_TOKEN_RESERVE


def resolve_limits(context_limit: int, scope: str = "first") -> RefLimits:
    """派发阈值。scope: first | interject。预算反推, 不写死字节数。

    首发: 单条 20% / 合计 40% / 拒绝 60%(北京老陈 2026-10-29 裁定)。
    插话: 单条与合计同值 5%, 不降级(超限直接拒绝)。
    """
    cfg = get_config().get("tuning.refs", {}) or {}
    _single_r = float(cfg.get("single_ratio", 0.20))
    _total_r = float(cfg.get("total_ratio", 0.40))
    _reject_r = float(cfg.get("reject_ratio", 0.60))
    _interject_r = float(cfg.get("interject_ratio", 0.05))
    base = budget_base_of(context_limit)
    single_t = int(base * _single_r)
    if scope == "interject":
        interject_t = int(base * _interject_r)
        return RefLimits(
            budget_base=base,
            single_cap_tokens=interject_t,
            total_cap_tokens=interject_t,
            reject_tokens=interject_t,   # 插话超限即拒绝, 拒绝线=上限
            interject_cap_tokens=interject_t,
            single_cap_chars=int(interject_t * CHARS_PER_TOKEN),
            read_max_bytes=int(interject_t * CHARS_PER_TOKEN),
        )
    return RefLimits(
        budget_base=base,
        single_cap_tokens=single_t,
        total_cap_tokens=int(base * _total_r),
        reject_tokens=int(base * _reject_r),
        interject_cap_tokens=int(base * _interject_r),
        single_cap_chars=int(single_t * CHARS_PER_TOKEN),
        read_max_bytes=int(single_t * CHARS_PER_TOKEN),
    )
