# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-17 小健 新建: 14.9.2 目录树【待补代码】装配线 + 14.9.6 K3 trim_orphan_pairs_proactive
"""compaction.assembler — 装配适配(保尾区保留 + 压缩消息注入 + 配对修剪) — 小健 2026-08-17

职责(SRP): 仅承载「装配」三步:
  - split_history_window: 按 tail_start 切出 {old_head, tail_part, absolute_tail_start}
  - inject_compressed_summary: 用摘要 assistant 消息替换 old_head, 保 system + 摘要 + tail + 最新 task
  - trim_orphan_pairs_proactive: FC 配对前置修剪(K3, 设计文档 [4] 14.9.6 K3)
设计文档: [4] 14.5 装配过滤(tail_start_id 之后原样保留、之前被摘要覆盖) + 14.9.6 K3 + 10.1.8 S5。

装配只编排注入/保留, 摘要生成归 summary; K3 复用既有 _trim_fc_pairs 思路(不重造);
old_head 原样保留(不破坏原库), 摘要仅运行时回填(list 组合新列表, 不改入参);
trim_orphan_pairs_proactive 与 value_first_prune(C3 prune 删 tool)协同闭环保配对。
"""
from typing import List, Dict, Tuple

from app.services.agent.compaction.split_turn import find_tail_start, preserve_recent_budget


def split_history_window(messages: List[Dict], context_limit: int,
                         reserve: int) -> Tuple[List[Dict], List[Dict], int]:
    """把历史切为 {old_head(待压缩), tail_part(保尾原样保留), absolute_tail_start} — 小健 2026-08-17

    适用场景: C4 锚定摘要压缩前, 把对话历史切成"待压缩旧段 + 保尾新区"。
    使用方法: 对消息列表 + 模型上下文/预留调用, 返回三要素供后续注入摘要。
    输入: messages 消息列表; context_limit 模型上下文上限; reserve 输出预留 buffer。
    输出: (old_head 待压缩段, tail_part 保尾段, absolute_tail_start 保尾起点下标)。
    前置条件: context_limit > reserve; messages 非空。
    设计文档: [4] 14.3.2 select() 返回 {head, tail_start_id} + 14.5 装配过滤。
    """
    budget = preserve_recent_budget(max(1, context_limit - reserve))
    tail_start = find_tail_start(messages, budget)
    old_head = messages[:tail_start]
    tail_part = messages[tail_start:]
    return old_head, tail_part, tail_start


def extract_new_block(messages: List[Dict], last_tail_start: int) -> List[Dict]:
    """提取 tail_start 之后的增量块(供 generate_chunked_summary) — 小健 2026-08-17

    适用场景: C5 增量块式摘要时, 取上次压缩之后新增的对话段喂 LLM(降本)。
    使用方法: 传完整消息列表 + 上次保尾起点, 返回其后增量段。
    输入: messages 消息列表; last_tail_start 上次保尾起点下标。
    输出: messages[last_tail_start:] 增量块列表。
    前置条件: 0 <= last_tail_start <= len(messages)。
    设计文档: [4] 14.9.6 C5「new_block 由 assembler 切分(tail_start 之后的增量)」。
    """
    return messages[last_tail_start:]


def inject_compressed_summary(messages: List[Dict], summary_text: str,
                              tail_start: int, keep_tail: int = 1) -> List[Dict]:
    """用摘要 assistant 消息替换 old_head, 保 system + 摘要 + tail + 最新 task — 小健 2026-08-17

    适用场景: 摘要生成后, 把待压缩旧段替换为摘要消息, 端到端完成压缩回填。
    使用方法: 传原消息 + 摘要文本 + 保尾起点, 返回新列表(不改动入参 messages)。
    输入: messages 消息列表; summary_text 摘要文本; tail_start 保尾起点; keep_tail 保尾最新条数(默认1)。
    输出: 新列表 = system 段 + 摘要 assistant 消息 + 保尾最新 keep_tail 条。
    前置条件: summary_text 非空(为空则原样返回 messages, 零退化)。
    设计文档: [4] 14.5「tail_start_id 之后原样保留, 之前被摘要覆盖」; 10.1.7 ⑤「保 system + 最新 task」。
    不改动入参(messages)(不破坏原库, 对应 14.3 "压缩截断不破坏原库")。
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

    适用场景: 凡做删除式裁剪(C3 prune 删 tool / value_first_prune)必须随后调用, 保 FC 配对。
    使用方法: 对裁剪后的消息列表调用, 返回清理孤儿后的新列表。
    输入: messages 消息列表。
    输出: 过滤后的新列表——只保留有对应 tool_call_id 的 tool 消息、及 tool_calls 全部有对应 tool 的 assistant。
    前置条件: 无; 防孤儿 assistant(tool_calls) 无对应 tool 致 LLM 400。
    设计文档: [4] 14.9.6 K3。
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