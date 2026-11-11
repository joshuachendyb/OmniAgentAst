# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-29 小欧 新建: 输入框引用阈值单一真源(从 DTO/resolver/budget/前端散落收口) — 小欧-2026-10-29
# 2026-10-30 小欧 三堂会审 A16: 配置比例钳制到 (0,1], 越界回落默认值(0/负数=全拒, >1=全放, 皆破坏预算) — 小欧-2026-10-30
# 2026-10-31 小欧 预算基准收口: budget_base_of 改调 agent_utils.trim_budget_base, 与 message_builder
#   裁剪预算同一真源(原两处各写一份 window-buffer-tools 减法) — 小欧-2026-10-31
# 2026-10-31 小欧 三堂会审 DRY: 四个预算比例默认值(0.20/0.40/0.60/0.05)原内联在本文件
#   resolve_limits, 与常量域分家; 收口至 app/constants(REF_*_RATIO), 本文件只做取值+钳制,
#   配置键 tuning.refs.* 仍可覆盖, 数值零变更 — 小欧-2026-10-31
# 2026-11-03 小欧 - 阈值比例非法回落默认 WARNING→INFO(配置容错) — 小欧-2026-11-03
"""services.refs.limits — 引用预算阈值的唯一真源

职责(单一职责): 由「本次生效模型的 context_length」派生出引用链路需要的全部阈值:
  单条上限/合计上限/拒绝线(首发) + 插话上限(interject) + 字符上限 + MAX_REFS。
为何独立: 阈值散在 DTO/resolver/budget/前端四处的历史已实测分叉(2MB 在 models.py:19 与
  browse_service.py:112 两处独立取值, 口径已分家); 本模块成为唯一入口, 改阈值只改一处。
不读盘、不裁内容: 纯计算; 磁盘读取与内容降级归 resolver/budget, 职责边界不越。
"""
from dataclasses import dataclass

from app.config import get_config

# 2026-10-31 小欧: 四个预算比例默认值单一真源在常量域(配置 tuning.refs.* 可覆盖) — 小欧-2026-10-31
from app.constants import (
    REF_INTERJECT_RATIO,
    REF_REJECT_RATIO,
    REF_SINGLE_RATIO,
    REF_TOTAL_RATIO,
)
from app.logger import logger

# 2026-10-31 小欧: 预算基准算式收口(与裁剪域同源); CHARS_PER_TOKEN 迁至 agent_utils(与估算代码同址)
from app.services.agent.agent_utils import CHARS_PER_TOKEN, trim_budget_base

# 引用条数上限: 前端入队即拦、后端 DTO 再拦(双保险, 防止任意条引用直入 prompt)
MAX_REFS = 20


@dataclass(frozen=True)
class RefLimits:
    """一批阈值(预算基准派生)。全部只读, 供 resolver/budget/orchestrator 消费。"""
    budget_base: int          # 预算基准 = context_length - compaction_buffer - tools_token_reserve
    single_cap_tokens: int    # 首发单条上限(预算×0.20)
    total_cap_tokens: int     # 首发合计上限(预算×0.40)
    reject_tokens: int        # 首发拒绝线(预算×0.60)
    interject_cap_tokens: int # 插话单条与合计同值(预算×0.05)
    single_cap_chars: int     # 单条字符上限(= 单条上限×CHARS_PER_TOKEN)
    read_max_bytes: int       # 单条读取字节上限(= 单条字符上限, 保守 1 字符 1 字节)


def budget_base_of(context_length: int) -> int:
    """预算基准: 窗口 - 输出缓冲 - tools预留。与 trim_history 同源口径。

    2026-10-29 小欧 - 运行时化: context_length 由 agent_runner.py:627 用 llm_service.context_length
    覆盖 MAX_CONTEXT_TOKENS, 故本函数必须接收运行时值, 禁写死 262144/212144。
    2026-10-31 小欧 - 算式收口: 直调 agent_utils.trim_budget_base(与 message_builder._trim_signal
    同一真源), 引用域与裁剪域的预算口径不再各写一份 — 小欧-2026-10-31
    2026-11-01 小欧 - 键名统一: context_limit → context_length — 小欧-2026-11-01
    """
    return trim_budget_base(context_length)


def _ratio_of(cfg: dict, key: str, default: float) -> float:
    """取配置比例并钳制: 必须落在 (0,1], 否则回落默认值。

    0/负数会让整条预算归零(全拒), >1 会让上限超过窗口(全放), 两者都破坏
    "引用不挤占上下文"的约束, 故非法值一律回落默认并留 warning 可查。
    """
    raw = cfg.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.info("[refs] 阈值比例非法(%s=%r), 回落默认 %s", key, raw, default)  # 2026-11-03 小欧: 配置容错, 降 INFO
        return default
    if not 0 < value <= 1:
        logger.warning("[refs] 阈值比例越界(%s=%s), 回落默认 %s", key, value, default)
        return default
    return value


def resolve_limits(context_length: int, scope: str = "first") -> RefLimits:
    """派发阈值。scope: first | interject。预算反推, 不写死字节数。

    首发: 单条 20% / 合计 40% / 拒绝 60%(北京老陈 2026-10-29 裁定)。
    插话: 单条与合计同值 5%, 不降级(超限直接拒绝)。
    """
    cfg = get_config().get("tuning.refs", {}) or {}
    _single_r = _ratio_of(cfg, "single_ratio", REF_SINGLE_RATIO)
    _total_r = _ratio_of(cfg, "total_ratio", REF_TOTAL_RATIO)
    _reject_r = _ratio_of(cfg, "reject_ratio", REF_REJECT_RATIO)
    _interject_r = _ratio_of(cfg, "interject_ratio", REF_INTERJECT_RATIO)
    base = budget_base_of(context_length)
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
