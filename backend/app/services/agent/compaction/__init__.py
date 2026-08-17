# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: compaction 模块统一导出(19.4.2 目录树规划)
#   2026-08-17 小健 落地: 补齐全量函数导出(触发/剪枝/摘要/切分/装配/冷却/修剪), 对齐 [4] 14.9.2 目录树
#   2026-08-17 小健 改名: 8 函数名符其实全量同步(import 块 + __all__ + 模块能力集描述)
#   2026-08-17 小健 注释同步(常量归属迁移): "专属常量 constants.py + re-export" 描述改为指向 agent 层根 compaction_constants.py 权威定义(迁出载体避免 __init__ 重链)
"""compaction 压缩/裁剪模块 — 统一导出 — 小欧 2026-08-16 / 小健 2026-08-17

模块能力集([4] 14.9.2 目录树 + 14.9.6 归并总览):
  - 触发判定: trigger.py      CompactionTrigger / should_compact_now / CompactionCooldown
  - 剪枝压缩: prune.py        clear_tool_outputs / use_tool_summary / compress_long_tool_output / keep_valuable_messages
  - 语义摘要: summary.py      generate_anchored_summary(C4, 唯一接入主链路) / generate_chunked_summary(降本变体)
  - 固定模板: summary_prompt  SUMMARY_TEMPLATE
  - 保尾切分: split_turn.py   preserve_recent_budget / find_tail_start / truncate_oversized_message
  - 装配修剪: assembler.py    split_history_window / get_new_messages_since / inject_compressed_summary
                              / remove_dangling_tool_calls
  - 专属常量: 见 ../compaction_constants.py(agent 层根, 压缩裁剪核心阈值权威定义; 迁出载体避免 __init__ 重链) — 小健 2026-08-17
"""
from app.services.agent.compaction.assembler import (
    get_new_messages_since,
    inject_compressed_summary,
    split_history_window,
    remove_dangling_tool_calls,
)
from app.services.agent.compaction.prune import (
    clear_tool_outputs,
    compress_long_tool_output,
    keep_valuable_messages,
    use_tool_summary,
)
from app.services.agent.compaction.split_turn import (
    find_tail_start,
    preserve_recent_budget,
    truncate_oversized_message,
)
from app.services.agent.compaction.summary import (
    generate_anchored_summary,
    generate_chunked_summary,
)
from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE
from app.services.agent.compaction.trigger import (
    CompactionCooldown,
    CompactionTrigger,
    should_compact_now,
)

__all__ = [
    # 触发判定
    "CompactionTrigger",
    "should_compact_now",
    "CompactionCooldown",
    # 剪枝压缩
    "clear_tool_outputs",
    "use_tool_summary",
    "compress_long_tool_output",
    "keep_valuable_messages",
    # 语义摘要
    "generate_anchored_summary",
    "generate_chunked_summary",
    "SUMMARY_TEMPLATE",
    # 保尾切分
    "preserve_recent_budget",
    "find_tail_start",
    "truncate_oversized_message",
    # 装配修剪
    "split_history_window",
    "get_new_messages_since",
    "inject_compressed_summary",
    "remove_dangling_tool_calls",
]