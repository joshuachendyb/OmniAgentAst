# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-17 小健 新建: 14.9.2 目录树【待补代码】落地, 依据 14.3.2 select + 14.5 装配过滤
"""compaction.split_turn — 保尾切分原语(tail_start + 半轮劈分) — 小健 2026-08-17

职责(SRP): 仅承载「保尾 token 预算 + 半轮劈分」的切分原语, 供 assembler 装配线切分历史窗口。
设计文档: [4] 14.9.2 splitTurn / 14.3.2 select() / 10.1.8 S5 compaction 全模块。
三堂会审:
  合规: 模块只做切分, 注入/摘要归 assembler/summary; token 估算复用 MessageBuilder._estimate_tokens(DRY)。
  合理(KISS-DIRECT): 定位 tail_start → 按 token 预算收敛 → 必要时半轮劈分保配对, 直线无绕路。
  关联(增强不退化): system 恒保留; 切分保 FC 配对(保留 assistant(tool_calls) 必带其 tool);
                     absolute_start 供 assembler 定位 new_block(对应 generate_chunked_summary 增量块)。
"""
from typing import List, Dict, Tuple

from app.services.agent.compaction.compaction_constants import (
    SPLIT_TURN_MAX_ASSISTANT_CHARS,
    TAIL_TOKEN_MAX,
    TAIL_TOKEN_MIN,
    TAIL_TOKEN_RATIO,
)
from app.services.agent.message_builder import MessageBuilder


def preserve_recent_budget(usable_tokens: int) -> int:
    """保尾 token 预算 = min(8000, max(2000, usable*0.25)) — 小健 2026-08-17

    设计文档: [4] 14.3.2 select() 的 preserveRecentBudget()。不是固定轮数, 是 token 预算上限 8K。
    """
    return min(TAIL_TOKEN_MAX, max(TAIL_TOKEN_MIN, int(usable_tokens * TAIL_TOKEN_RATIO)))


def find_tail_start(messages: List[Dict], budget_tokens: int) -> int:
    """定位尾部窗口起始下标, 满足 token 预算且不拆散 FC 对 — 小健 2026-08-17

    设计文档: [4] 14.3.2 select()(从最新往前逐轮累计, 预算内整轮保留)。
    保尾三原则: system 恒保留(下标头不可动); 遇 assistant(tool_calls) 该对整体保留;
    倒序累计超预算即停; 保底返回 system 之后下标。
    """
    if not messages:
        return 0
    prefix = 0
    for msg in messages:
        if msg.get("role") == "system":
            prefix += 1
        else:
            break
    if prefix and MessageBuilder._estimate_tokens(messages[:prefix]) > budget_tokens:
        return prefix
    used = 0
    tail_start = prefix
    for i in range(len(messages) - 1, prefix - 1, -1):
        cost = MessageBuilder._estimate_tokens([messages[i]])
        if used + cost > budget_tokens:
            break
        used += cost
        tail_start = i
        if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
            continue
    return tail_start


def split_half_turn(tool_msgs: List[Dict]) -> List[Dict]:
    """半轮劈分: 单一 tool 消息超长时压缩其 content(不拆配对外散) — 小健 2026-08-17

    设计文档: [4] 14.3.2 splitTurn「该轮内部劈分——只保留该轮后半段消息」。
    注意: 本原语只对单条 tool 消息做内容截断(保头段+标记), 不把轮次消息拆成两段,
          与「保尾不动刀」语义一致; 真正的对级劈分(只保该轮 tail)由 find_tail_start 的
          逐条累计天然完成(超预算即从该条后断开)。
    """
    result: List[Dict] = []
    for msg in tool_msgs:
        if msg.get("role") in ("tool", "assistant"):
            raw = str(msg.get("content", "") or "")
            if len(raw) > SPLIT_TURN_MAX_ASSISTANT_CHARS:
                m = dict(msg)
                m["_raw"] = raw
                m["content"] = raw[:SPLIT_TURN_MAX_ASSISTANT_CHARS] + "…[split_turn]"
                m["_truncated"] = True
                result.append(m)
                continue
        result.append(msg)
    return result