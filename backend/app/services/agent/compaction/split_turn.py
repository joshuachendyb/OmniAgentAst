# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-17 小健 新建: 14.9.2 目录树【待补代码】落地, 依据 14.3.2 select + 14.5 装配过滤
#   2026-08-17 小健 补全: 各函数 docstring 补全适用场景/使用方法/前置条件/输入输出(043ed9c54)
#   2026-08-17 小健 改名: split_half_turn→truncate_oversized_message(名符其实); 模块函数引用同步
"""compaction.split_turn — 保尾切分原语(tail_start + 半轮劈分) — 小健 2026-08-17

职责(SRP): 仅承载「保尾 token 预算 + 半轮劈分」的切分原语, 供 assembler 装配线切分历史窗口。
设计文档: [4] 14.9.2 splitTurn / 14.3.2 select() / 10.1.8 S5 compaction 全模块。

切分只做位置/预算计算, 注入与摘要归 assembler/summary; token 估算复用 MessageBuilder._estimate_tokens(DRY);
system 恒保留, 切分保 FC 配对(保留 assistant(tool_calls) 必带其 tool);
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

    适用场景: 任何需要"保尾 token 预算"处的统一计算(如 split_history_window 算保尾窗口)。
    使用方法: 传可用预算 token 数, 返回夹取后的保尾预算。
    输入: usable_tokens 可用预算 token 数。
    输出: int 保尾预算, 范围 [TAIL_TOKEN_MIN=2000, TAIL_TOKEN_MAX=8000]。
    前置条件: 无; 不是固定轮数而是 token 预算上限 8K。
    设计文档: [4] 14.3.2 select() 的 preserveRecentBudget()。
    """
    return min(TAIL_TOKEN_MAX, max(TAIL_TOKEN_MIN, int(usable_tokens * TAIL_TOKEN_RATIO)))


def find_tail_start(messages: List[Dict], budget_tokens: int) -> int:
    """定位尾部窗口起始下标, 满足 token 预算且不拆散 FC 对 — 小健 2026-08-17

    适用场景: 压缩前确定保尾区的起点下标(该下标之后原样保留)。
    使用方法: 传消息列表 + 保尾预算, 返回尾部起点下标(供切片 messages[:start]/[start:])。
    输入: messages 消息列表; budget_tokens 保尾 token 预算。
    输出: int 保尾起点下标; 空列表返回 0。
    前置条件: 无; 保尾三原则——system 恒保留(下标头不可动); 遇 assistant(tool_calls) 该对整体保留;
              倒序累计超预算即停; 保底返回 system 之后下标。
    设计文档: [4] 14.3.2 select()(从最新往前逐轮累计, 预算内整轮保留)。
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


def truncate_oversized_message(tool_msgs: List[Dict]) -> List[Dict]:
    """半轮劈分: 单一 tool 消息超长时压缩其 content(不拆配对外散) — 小健 2026-08-17

    适用场景: 超长单条 tool/assistant 消息需控窗但又不想拆散 FC 对时, 对该条做头部截断。
    使用方法: 传该轮的消息列表, 返回截断处理后的新列表(超长条保留头段+标记)。
    输入: tool_msgs 单轮消息列表。
    输出: 新列表; 超长条(>SPLIT_TURN_MAX_ASSISTANT_CHARS=4000)截为头段 + "…[split_turn]",
          带 `_raw` 原内容与 `_truncated=True` 标记。
    前置条件: 无; 只对单条消息做内容截断, 不把轮次消息拆成两段(与「保尾不动刀」语义一致);
              真正的对级劈分由 find_tail_start 逐条累计天然完成。
    设计文档: [4] 14.3.2 splitTurn「该轮内部劈分——只保留该轮后半段消息」。
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