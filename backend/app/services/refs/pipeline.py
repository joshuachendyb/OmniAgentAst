# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: 引用"解析→体积裁决→回执汇集"唯一流水线, 首发与插话共用 — 小欧-2026-10-30

"""services.refs.pipeline — 引用处理流水线(首发/插话唯一实现)

为什么需要: 编排层原先两处各写一遍 resolve → budget → 回执汇集, 且**两处顺序不同**
  (插话漏了 resolver 的 dropped 条目, 只在日志里点名, 用户看不到"哪个文件读不出来")。
  收口到一个函数后, 顺序被固定为: 入口过滤(sanitize) → 读取失败(resolver dropped)
  → 读取期回执(截断/区间裁剪) → 体积裁决(budget) —— 即"先判生死, 再报异常", 与
  回执文案里"全部不可用"的判定口径一致。

不做的事(SRP): 不解析 limits(窗口来源不同: 首发看 agent.llm_client, 插话看目标任务 agent),
  不下发回执/不构造错误帧(载体不同: 首发 yield 到本次流, 插话 publish 到目标任务缓冲),
  不写日志(两处日志字段不同)。
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.refs.budget import budget_refs
from app.services.refs.limits import RefLimits
from app.services.refs.resolver import resolve_refs


async def prepare_refs(
    refs: Optional[List[Dict[str, Any]]],
    *,
    limits: RefLimits,
    scope: str,
    sanitized_dropped: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """解析 + 体积裁决, 返回 (放行条目, 回执条目)。

    回执条目顺序固定: resolver 丢弃 → resolver 提示(截断/区间裁剪) → budget 裁决 →
    入口过滤丢弃(sanitize)。条目只带 label/path/reason/detail, 级别由 build_notice 统一裁决。
    """
    resolved, r_dropped, r_notices = await resolve_refs(refs, limits=limits)
    final, b_notices = budget_refs(resolved, limits=limits, scope=scope)
    notices = list(r_dropped) + list(r_notices) + list(b_notices) + list(sanitized_dropped or ())
    return final, notices
