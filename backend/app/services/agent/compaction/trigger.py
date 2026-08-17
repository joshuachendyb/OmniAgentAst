# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: 统一触发判定(14.9.3① 三条件) + 动态窗口触发(14.9.6 K1) + 冷却节流(14.9.6 K2)
#   2026-08-17 小健 落地: 三函数合并 trigger.py, 常量自 compaction.compaction_constants(DRY re-export 全局缓冲常量)
"""compaction.trigger — 触发判定(统一/窗口/冷却) — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「是否该压缩」的三类判定, 不含任何压缩/裁剪执行逻辑。
依据: [4] 14.9.3① / 14.9.6 K1/K2。

三个函数关系:
  - CompactionTrigger.should_compact: 三条件(模型窗口/增量/绝对值)统一判定, 供 C3 剪枝触发。
  - should_compact_window: 大窗口下消息数兜底触发(K1), 供 t1_compress_observations/T1 补触发。
  - CompactionCooldown: 压缩后冷却节流(K2), 防 C4 每轮烧 LLM; 与 trigger 解耦(trigger 管"该不该",
    cooldown 管"刚压过没")。
"""
from typing import List

from app.services.agent.compaction.compaction_constants import (
    COMPACTION_BUFFER,
    COOLDOWN_ROUNDS,
    MAX_CONTEXT_RATIO,
    TRIGGER_MAX_MSGS,
)

# ---- CompactionTrigger: 统一触发判定(14.9.3①) ————————————————————————————


class CompactionTrigger:
    """统一触发判定 — 小欧 2026-08-16

    三个独立条件, 满足任一即触发压缩(先用剪枝, 剪枝后仍超限再由上层决定是否锚定摘要):
      A. 模型窗口: current_tokens >= usable(context_limit - reserve)
      B. 增量:     本轮粗估 - 上轮精确(last_total_tokens) > COMPACTION_BUFFER
      C. 绝对值:   current_tokens >= context_limit * MAX_CONTEXT_RATIO
    """

    def should_compact(self, current_tokens: int, last_total_tokens: int,
                       context_limit: int, reserve: int) -> bool:
        usable = context_limit - reserve
        delta = current_tokens - last_total_tokens
        if current_tokens >= usable:
            return True
        if delta > COMPACTION_BUFFER:
            return True
        if current_tokens >= int(context_limit * MAX_CONTEXT_RATIO):
            return True
        return False


# ---- should_compact_window: 动态窗口触发(14.9.6 K1) —————————————————————————


def should_compact_window(current_tokens: int, context_limit: int,
                          reserve: int, msg_count: int,
                          max_msgs: int = TRIGGER_MAX_MSGS) -> bool:
    """动态窗口触发, 大窗口下消息数兜底 — 小欧 2026-08-16"""
    usable = context_limit - reserve
    if current_tokens >= usable:
        return True
    if msg_count >= max_msgs:        # 大窗口下消息数兜底触发, 防"不触发"
        return True
    return False


# ---- CompactionCooldown: 触发冷却节流(14.9.6 K2) ——————————————————————————


class CompactionCooldown:
    """压缩冷却节流, 防连续轮次反复压缩 — 小欧 2026-08-16"""

    def __init__(self, cooldown_rounds: int = COOLDOWN_ROUNDS):
        self._cooldown_rounds = cooldown_rounds
        self._since_last = 0

    def allow(self) -> bool:
        self._since_last += 1
        return self._since_last > self._cooldown_rounds

    def mark_compacted(self) -> None:
        self._since_last = 0