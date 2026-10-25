# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: 统一触发判定(14.9.3① 三条件) + 动态窗口触发(14.9.6 K1) + 冷却节流(14.9.6 K2)
#   2026-08-17 小健 落地: 三函数合并 trigger.py, 常量自 agent.compaction_constants(DRY)
#   2026-08-17 小健 补全: 各函数 docstring 补全适用场景/使用方法/前置条件/输入输出(043ed9c54)
#   2026-08-17 小健 改名: should_compact_window→should_compact_now(名符其实); 函数关系/设计文档引用同步
#   2026-08-17 小健 常量归属迁移(北京老陈驱动): 压缩/裁剪常量权威迁至 agent 层根 compaction_constants.py, 本模块导入路径由 compaction.compaction_constants 改为 app.services.agent.compaction_constants
#   2026-08-17 小健 阈值重构(北京老陈 2026-08-17 定案, loop裁剪=上下文×3/4): 绝对值安全网条件C int(context_limit*MAX_CONTEXT_RATIO)→int(context_limit*TRIM_TRIGGER_RATIO); 导入 MAX_CONTEXT_RATIO→TRIM_TRIGGER_RATIO
#   2026-09-23 小欧 trim配置化: should_compact 每次调用读 tuning.trim.compaction_buffer/trigger_ratio 兜底常量（无状态类与 message_builder 一致）
#   2026-10-25 23:29 小欧 删 CompactionTrigger 类(should_compact 死代码): 全仓零调用方(仅 __init__ 导出), 公式 context_limit×ratio 与 trim_history 新口径 budget_base×ratio 分叉留则埋雷; should_compact_now/CompactionCooldown 保留(预留能力, 不涉 TRIM_TRIGGER_RATIO 公式)
"""compaction.trigger — 触发判定(窗口/冷却) — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「是否该压缩」的判定(动态窗口触发 + 冷却节流), 不含任何压缩/裁剪执行逻辑。
依据: [4] 14.9.3① / 14.9.6 K1/K2。

两个函数关系(CompactionTrigger 已删, 见编辑历史):
  - should_compact_now: 大窗口下消息数兜底触发(K1), 供 compress_long_tool_output/keep_valuable_messages 补触发。
  - CompactionCooldown: 压缩后冷却节流(K2), 防 C4 每轮烧 LLM; 与触发解耦(触发管"该不该", cooldown 管"刚压过没")。
"""
from typing import List

from app.services.agent.compaction_constants import (
    COOLDOWN_ROUNDS,
    TRIGGER_MAX_MSGS,
)

# ---- should_compact_now: 动态窗口触发(14.9.6 K1) —————————————————————————


def should_compact_now(current_tokens: int, context_limit: int,
                       reserve: int, msg_count: int,
                       max_msgs: int = TRIGGER_MAX_MSGS) -> bool:
    """动态窗口触发, 大窗口下消息数兜底 — 小欧 2026-08-16

    适用场景: 超大上下文窗口模型(如 900K)下, 固定比例阈值形同虚设时用; 供 compress_long_tool_output/keep_valuable_messages 补触发。
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
    前置条件: 无; 与触发判定解耦, 可单独组合(触发管"该不该", cooldown 管"刚压过没")。
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