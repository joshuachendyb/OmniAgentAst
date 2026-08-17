# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: compaction 模块统一导出(19.4.2 目录树规划)
#   2026-08-17 小健 落地: 补齐全量函数导出(触发/剪枝/摘要/切分/装配/冷却/修剪), 对齐 [4] 14.9.2 目录树
"""compaction 压缩/裁剪模块 — 统一导出 — 小欧 2026-08-16 / 小健 2026-08-17

模块能力集([4] 14.9.2 目录树 + 14.9.6 归并总览):
  - 触发判定: trigger.py      CompactionTrigger / should_compact_window / CompactionCooldown
  - 剪枝压缩: prune.py        prune_tool_outputs / t1_reuse_summary / t1_compress_observations / value_first_prune
  - 语义摘要: summary.py      generate_anchored_summary(C4, 唯一接入主链路) / generate_chunked_summary(降本变体)
  - 固定模板: summary_prompt  SUMMARY_TEMPLATE
  - 保尾切分: split_turn.py   preserve_recent_budget / find_tail_start / split_half_turn
  - 装配修剪: assembler.py    split_history_window / extract_new_block / inject_compressed_summary
                              / trim_orphan_pairs_proactive
  - 专属常量: constants.py    压缩裁剪专属常量 + re-export 全局缓冲常量(DRY)
"""
from app.services.agent.compaction.assembler import (
    extract_new_block,
    inject_compressed_summary,
    split_history_window,
    trim_orphan_pairs_proactive,
)
from app.services.agent.compaction.prune import (
    t1_compress_observations,
    t1_reuse_summary,
    prune_tool_outputs,
    value_first_prune,
)
from app.services.agent.compaction.split_turn import (
    find_tail_start,
    preserve_recent_budget,
    split_half_turn,
)
from app.services.agent.compaction.summary import (
    generate_anchored_summary,
    generate_chunked_summary,
)
from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE
from app.services.agent.compaction.trigger import (
    CompactionCooldown,
    CompactionTrigger,
    should_compact_window,
)

__all__ = [
    # 触发判定
    "CompactionTrigger",
    "should_compact_window",
    "CompactionCooldown",
    # 剪枝压缩
    "prune_tool_outputs",
    "t1_reuse_summary",
    "t1_compress_observations",
    "value_first_prune",
    # 语义摘要
    "generate_anchored_summary",
    "generate_chunked_summary",
    "SUMMARY_TEMPLATE",
    # 保尾切分
    "preserve_recent_budget",
    "find_tail_start",
    "split_half_turn",
    # 装配修剪
    "split_history_window",
    "extract_new_block",
    "inject_compressed_summary",
    "trim_orphan_pairs_proactive",
]