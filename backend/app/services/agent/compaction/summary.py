# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: C4 锚定摘要引擎(一次 LLM, 喂截断输出, 原库完整)
#   2026-08-17 小健 修正: 原伪代码 `call_llm_with_fallback(agent=llm_client,...)` 参数错、`str(getattr(data,...))`
#                       取不到文本。真实协议(llm_stream.py:265)为 async generator 产 ("response", resp) tuple,
#                       文本在 resp["content"]; 首参是 agent 对象(含 .llm_client)。按真实协议重写。
#   2026-08-17 小健 新增: generate_chunked_summary + _extract_response_content(C4 降本变体, 复用统一提取)
"""compaction.summary — C4: 锚定摘要压缩 + 增量块式锚定摘要(降本变体) — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 本文件仅承载「锚定/增量块摘要引擎」(调 LLM, 产出摘要文本, 不破坏原库)。
         触发/剪枝/装配/切分分别在 trigger.py / prune.py / assembler.py / split_turn.py。
依据: [4] 14.9.4② / 14.9.6 C5。
"""
from typing import List, Dict, Optional

from app.services.agent.compaction.compaction_constants import SUMMARY_FEED_MAX_CHARS
from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE


async def _extract_response_content(llm_agent, feed: List[Dict]) -> str:
    """调 call_llm_with_fallback 并提取最终文本(真实 async-generator 协议) — 小健 2026-08-17

    真实协议(llm_stream.py): call_llm_with_fallback(agent, messages, openai_tools) 为 async generator,
    item 即 tuple, item[0]=="response" 时 item[1]=resp dict, 文本在 resp["content"](见 _build_answer_response:126-129)。
    """
    from app.services.agent.llm_stream import call_llm_with_fallback

    content = ""
    async for item in call_llm_with_fallback(agent=llm_agent, messages=feed, openai_tools=None):
        if isinstance(item, tuple) and len(item) >= 2 and item[0] == "response":
            resp = item[1]
            if isinstance(resp, dict):
                c = str(resp.get("content") or "").strip()
                if c:
                    content = c
    return content


async def generate_anchored_summary(llm_agent, messages: List[Dict],
                                    previous_summary: Optional[str] = None) -> str:
    """一次 LLM 调用产出锚定摘要 — 小欧 2026-08-16

    适用场景: C4 锚定摘要压缩(当前唯一接入主链路); 长任务跨多轮/续聊需保决策链, 且已放开 R4 零 LLM 原则。
    使用方法: 由 react_cycle._compact_injected_history await 调用(传 agent + 对话历史); 也可独立对任意消息列表调用。
    输入: llm_agent Agent 对象(须含 .llm_client, 用于发起流式调用); messages 对话消息列表;
          previous_summary 可选上一轮摘要文本(用于增量锚定)。
    输出: str 锚定摘要文本(SUMMARY_TEMPLATE 六段 Markdown); 为空表示未产出(上层原样保留历史, 零退化)。
    前置条件: 须放开 R4(COMPACTION_ENABLED=True); tools=None 走 Text 模式不触发工具; 首参必须是 agent 对象而非 llm_client
              (否则 call_llm_with_fallback 缺 agent 上下文无法调用); 自动续跑由上层 react_cycle 发 Continue。
    """
    feed: List[Dict] = []
    for msg in messages:
        if msg.get("role") == "tool":
            c = str(msg.get("content", ""))[:SUMMARY_FEED_MAX_CHARS]
            feed.append({**msg, "content": c})
        else:
            feed.append(msg)
    prompt = SUMMARY_TEMPLATE + (f"\npreviousSummary:\n{previous_summary}" if previous_summary else "")
    feed = [{"role": "system", "content": prompt}, *feed]
    return await _extract_response_content(llm_agent, feed)


async def generate_chunked_summary(llm_agent, new_block: List[Dict],
                                   previous_summary: Optional[str] = None) -> str:
    """只把新增块喂 LLM, 与 previousSummary 合并 — 小欧 2026-08-16

    适用场景: C4 降本变体(备选); 长任务且会多次压缩时, 只摘要"新增块"避免全量重算, 成本随压缩次数线性。
    使用方法: 传 llm_agent + 新增块消息列表 + 可选上一轮摘要, await 返回摘要文本。
    输入: llm_agent Agent 对象(含 .llm_client); new_block 新增块消息列表(上次 compact 之后的新轮次);
          previous_summary 可选上一轮摘要。
    输出: str 增量合并后的摘要文本。
    前置条件: 同 generate_anchored_summary(须放开 R4、首参 agent 对象); 与 C4 区别仅在不重喂全量历史,
          只 new_block(tool 输出截断 2000) + previousSummary。
    """
    feed: List[Dict] = [{"role": "system", "content": SUMMARY_TEMPLATE}]
    if previous_summary:
        feed.append({"role": "user", "content": f"已有摘要:\n{previous_summary}"})
    for msg in new_block:
        c = str(msg.get("content", ""))[:SUMMARY_FEED_MAX_CHARS] if msg.get("role") == "tool" else str(msg.get("content", ""))
        feed.append({**msg, "content": c})
    return await _extract_response_content(llm_agent, feed)