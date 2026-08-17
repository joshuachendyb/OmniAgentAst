# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-17 小健 新建: 14.9.2 目录树【待补代码】装配线 + 14.9.6 K3 trim_orphan_pairs_proactive
"""compaction.assembler — 装配适配(保尾区保留 + 压缩消息注入 + 配对修剪) — 小健 2026-08-17

职责(SRP): 仅承载「装配」三步:
  - split_history_window: 按 tail_start 切出 {old_head, tail_part, absolute_tail_start}
  - inject_compressed_summary: 用摘要 assistant 消息替换 old_head, 保 system + 摘要 + tail + 最新 task
  - trim_orphan_pairs_proactive: FC 配对前置修剪(K3, 设计文档 [4] 14.9.6 K3)
设计文档: [4] 14.5 装配过滤(tail_start_id 之后原样保留、之前被摘要覆盖) + 14.9.6 K3 + 10.1.8 S5。
三堂会审:
  合规(SRP): 装配只编排注入/保留, 摘要生成归 summary; K3 复用既有 _trim_fc_pairs 思路(不重造)。
  合理(KISS): 三步直线: 切分 → 定位 → 替换, new_block=tail_start 之后增量(喂 generate_chunked_summary)。
  关联(增强不退化): old_head 原样保留(不破坏原库), 摘要仅运行时回填(list 组合新列表);
                     trim_orphan_pairs_proactive 与 value_first_prune(C3 prune 删 tool)协同闭环保配对。
"""
from typing import List, Dict, Tuple

from app.services.agent.compaction.split_turn import find_tail_start, preserve_recent_budget


def split_history_window(messages: List[Dict], context_limit: int,
                         reserve: int) -> Tuple[List[Dict], List[Dict], int]:
    """把历史切为 {old_head(待压缩), tail_part(保尾原样保留), absolute_tail_start} — 小健 2026-08-17

    设计文档: [4] 14.3.2 select() 返回 {head, tail_start_id} + 14.5 装配过滤。
    """
    budget = preserve_recent_budget(max(1, context_limit - reserve))
    tail_start = find_tail_start(messages, budget)
    old_head = messages[:tail_start]
    tail_part = messages[tail_start:]
    return old_head, tail_part, tail_start


def extract_new_block(messages: List[Dict], last_tail_start: int) -> List[Dict]:
    """提取 tail_start 之后的增量块(供 generate_chunked_summary) — 小健 2026-08-17

    设计文档: [4] 14.9.6 C5 关联逻辑「new_block 由 assembler 切分(tail_start 之后的增量)」。
    """
    return messages[last_tail_start:]


def inject_compressed_summary(messages: List[Dict], summary_text: str,
                              tail_start: int, keep_tail: int = 1) -> List[Dict]:
    """用摘要 assistant 消息替换 old_head, 保 system + 摘要 + tail + 最新 task — 小健 2026-08-17

    设计文档: [4] 14.5「tail_start_id 之后原样保留, 之前被摘要覆盖」;
             10.1.7 ⑤ 回填逻辑「保 system + 最新 task」。
    返回新列表, 不改动入参(messages)(不破坏原库, 对应 14.3 "压缩截断不破坏原库")。
    """
    if not summary_text:
        return messages
    system_msgs = [m for m in messages[:tail_start] if m.get("role") == "system"]
    tail_msgs = messages[tail_start:]
    # 保最新 tail 条(通常为用户最新 task), 避免摘要顶掉最新输入
    if len(tail_msgs) > keep_tail:
        tail_msgs = tail_msgs[-keep_tail:]
    return system_msgs + [{"role": "assistant", "content": summary_text}] + tail_msgs


def trim_orphan_pairs_proactive(messages: List[Dict]) -> List[Dict]:
    """保留有对应 tool_call_id 的工具消息, 删孤儿 assistant/tool — 小健 2026-08-17

    设计文档: [4] 14.9.6 K3。凡做删除式裁剪(C3 prune 删 tool / value_first_prune)必配:
    删消息后立即保 FC 配对, 防孤儿 assistant(tool_calls) 无对应 tool 致 LLM 400。
    """
    seen_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    result: List[Dict] = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            keep = all(tc.get("id") in seen_ids for tc in m["tool_calls"])
            if keep:
                result.append(m)
            continue
        if m.get("role") == "tool":
            if m.get("tool_call_id") in seen_ids:
                result.append(m)
            continue
        result.append(m)
    return result