# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: 引用合计体积裁决(纯计算) — 小欧-2026-10-30
# 2026-10-30 小欧 三堂会审口径: C 档改**单轮等比压缩**(factor=合计上限/当前合计, 每条最低
#   REF_MIN_KEEP_LINES 行, 不迭代), 压后仍超拒绝线才拒绝 — 小欧-2026-10-30

"""services.refs.budget — 引用合计体积裁决(纯计算, 零 IO)

三档(4.7.3):
  A 原样   合计 ≤ total_cap      → 全文
  B 摘录   单条超上限           → 读取期已按头尾摘录(4.6.3), 此处只做合计判定
  C 压缩   合计 > total_cap      → 单轮等比压缩: 每条按 factor 保留头尾, 最低 REF_MIN_KEEP_LINES 行
  拒绝     C 之后仍 > reject_tokens → 全批拒绝 + 回执(兜底; 正常由 MAX_REFS/单条上限提前挡住)
插话(scope=interject): 单条与合计同值 5%, 超限即拒绝, 不降级。

为何单轮等比而非迭代: 迭代压缩每轮都要重算总长并再切片, 逻辑绕且收益不明; 一次按比例
  落到目标即可, 压完仍超由拒绝线兜底(断言式)。
"""
from typing import Any, Dict, List, Tuple

from app.constants import REF_HEAD_RATIO, REF_MIN_KEEP_LINES, REF_TAIL_RATIO
from app.services.agent.compaction_constants import CHARS_PER_TOKEN
from app.services.refs.clip import clip_lines
from app.services.refs.limits import RefLimits

# clip_lines 只保留 keep_lines 的头 REF_HEAD_RATIO / 尾 REF_TAIL_RATIO(合计 80%),
#   故要落到"目标行数"需按该比例反推入参
_CLIP_KEEP_RATIO = REF_HEAD_RATIO + REF_TAIL_RATIO


def _tokens_of(content: str) -> int:
    """估算 token: 字符数 / CHARS_PER_TOKEN(唯一真源 compaction_constants, DRY)。"""
    return int(len(content or "") / CHARS_PER_TOKEN)


def _reject_all(resolved: List[Dict[str, Any]], detail: str) -> List[Dict[str, str]]:
    """整批拒绝的回执条目(reason 由 notice.build_notice 裁决为 error 级)。"""
    return [{
        "label": (r.get("label") or r.get("path") or ""),
        "path": r.get("path") or "",
        "reason": "rejected",
        "detail": detail,
    } for r in resolved]


def budget_refs(
    resolved: List[Dict[str, Any]],
    *,
    limits: RefLimits,
    scope: str = "first",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """裁决引用体积, 返回 (final_refs, notices)。

    final_refs = 通过裁决、进入 prompt 的引用(已含 content);
    notices    = {label, path, reason, detail}: compressed/rejected 回执(level 由 build_notice 补)。
    """
    notices: List[Dict[str, str]] = []
    if not resolved:
        return [], notices
    total = sum(_tokens_of(r.get("content") or "") for r in resolved)

    # 插话: 单条与合计同值 5%, 任一超限即整批拒绝(不降级, 4.7.4)
    if scope == "interject":
        cap = limits.interject_cap_tokens
        if total > cap or any(_tokens_of(r.get("content") or "") > cap for r in resolved):
            return [], _reject_all(resolved, "插话引用过大, 请改用行片段, 或等当前任务结束后再发")
        return resolved, notices

    # 首发 A 档: 合计未超 40%, 原样放行
    if total <= limits.total_cap_tokens:
        return resolved, notices

    # 首发 C 档: 单轮等比压缩, factor = 合计上限 / 当前合计
    factor = limits.total_cap_tokens / total
    kept: List[Dict[str, Any]] = []
    for r in resolved:
        content = r.get("content") or ""
        n_lines = content.count("\n") + 1
        if n_lines <= REF_MIN_KEEP_LINES:
            # 行数已到下限, 再摘就不可读 — 原样保留, 超限由下方拒绝线兜底
            kept.append(r)
            continue
        target = max(REF_MIN_KEEP_LINES, int(n_lines * factor))
        new_content, omitted = clip_lines(content, int(target / _CLIP_KEEP_RATIO))
        if not omitted:
            kept.append(r)
            continue
        kept.append({**r, "content": new_content})
        notices.append({
            "label": (r.get("label") or r.get("path") or ""),
            "path": r.get("path") or "",
            "reason": "compressed",
            "detail": f"已省略 {omitted} 行",
        })

    # 拒绝线兜底: 压缩后仍超 60%(断言式, 正常由 MAX_REFS/单条上限提前杜绝)
    if sum(_tokens_of(r.get("content") or "") for r in kept) > limits.reject_tokens:
        return [], _reject_all(resolved, "引用体积超出模型窗口, 请减少引用或改用行片段")
    return kept, notices
