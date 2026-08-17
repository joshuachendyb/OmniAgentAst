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

    适用场景: C3 剪枝压缩前的"是否该压缩"统一判定; 供 message_builder.trim_history 委托链或上层裁剪入口调用。
    使用方法: 实例化后调用 should_compact(), 传当前/上轮 token 数, 返回 bool 决定是否进入剪枝。
    前置条件: 无状态, 可随时实例化; 需要调用方提供准确的 current_tokens / last_total_tokens / context_limit / reserve。

    三个独立条件, 满足任一即触发压缩(先用剪枝, 剪枝后仍超限再由上层决定是否锚定摘要):
      A. 模型窗口: current_tokens >= usable(context_limit - reserve)
      B. 增量:     本轮粗估 - 上轮精确(last_total_tokens) > COMPACTION_BUFFER
      C. 绝对值:   current_tokens >= context_limit * MAX_CONTEXT_RATIO
    """

    def should_compact(self, current_tokens: int, last_total_tokens: int,
                       context_limit: int, reserve: int) -> bool:
        """是否触发压缩 — 小欧 2026-08-16

        输入: current_tokens 本轮粗估 token 数; last_total_tokens 上轮精确 total_tokens(可为 0);
              context_limit 模型上下文上限; reserve 输出预留 buffer。
        输出: bool —— True 需压缩, False 不需。
        前置条件: context_limit > reserve; last_total_tokens 无历史时传 0 只走 A/C 条件。
        """
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
    """动态窗口触发, 大窗口下消息数兜底 — 小欧 2026-08-16

    适用场景: 超大上下文窗口模型(如 900K)下, 固定比例阈值形同虚设时用; 供 t1_compress_observations/T1 补触发。
    使用方法: 直接调用, 传窗口 token 数 + 消息数, 返回是否该压缩。
    输入: current_tokens 当前 token 数; context_limit 模型上限; reserve 输出预留;
          msg_count 当前消息条数; max_msgs 消息数兜底阈值(默认 TRIGGER_MAX_MSGS=80)。
    输出: bool —— True 需压缩。
    前置条件: context_limit > reserve。
    """
    usable = context_limit - reserve
    if current_tokens >= usable:
        return True
    if msg_count >= max_msgs:        # 大窗口下消息数兜底触发, 防"不触发"
        return True
    return False


# ---- CompactionCooldown: 触发冷却节流(14.9.6 K2) ——————————————————————————


class CompactionCooldown:
    """压缩冷却节流, 防连续轮次反复压缩 — 小欧 2026-08-16

    适用场景: 启用 C4(LLM 压缩)时防连续轮次反复烧 LLM; 压缩后冷却若干轮再评估。
    使用方法: 实例化后, 每轮先调 allow() 问"能否压缩"; 执行压缩成功后调 mark_compacted() 复位冷却。
    前置条件: 无; 与 CompactionTrigger 解耦, 可单独组合(trigger 管"该不该", cooldown 管"刚压过没")。
    """

    def __init__(self, cooldown_rounds: int = COOLDOWN_ROUNDS):
        """输入: cooldown_rounds 冷却轮数(默认 COOLDOWN_ROUNDS=2); 无输出。 — 小欧 2026-08-16"""
        self._cooldown_rounds = cooldown_rounds
        self._since_last = 0

    def allow(self) -> bool:
        """本轮是否允许压缩 — 小欧 2026-08-16
        输入: 无; 输出: bool —— 距上次压缩已超 cooldown_rounds 返回 True。
        """
        self._since_last += 1
        return self._since_last > self._cooldown_rounds

    def mark_compacted(self) -> None:
        """记录本次已压缩(复位冷却计数) — 小欧 2026-08-16
        输入: 无; 输出: 无(内部将 _since_last 置 0)。
        """
        self._since_last = 0