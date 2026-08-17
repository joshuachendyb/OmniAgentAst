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

    tools=None 走 llm_stream Text 模式; 喂给 LLM 的 tool 输出截断 2000 字符(防再撑爆),
    原始 messages 完整保留(list 不变), 仅生成文本摘要返回。
    【签名修正 2026-08-17】首参由 llm_client 改为 llm_agent(agent 对象): 因 call_llm_with_fallback
    需要 agent.llm_client 发起流式调用, 传 llm_client 会缺 agent 上下文、无法正确调用。
    自动续跑由上层 react_cycle 发 Continue。
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

    与 C4 区别: 不重喂全量历史, 仅 new_block(tool 输出截断 2000) + previousSummary,
    成本随压缩次数线性而非累积。其余(截断喂/原库完整/previousSummary 锚定)同 14.9.4。
    【签名修正 2026-08-17】首参 llm_client→llm_agent(同 14.9.4②), 复用 _extract_response_content(DRY)。
    """
    feed: List[Dict] = [{"role": "system", "content": SUMMARY_TEMPLATE}]
    if previous_summary:
        feed.append({"role": "user", "content": f"已有摘要:\n{previous_summary}"})
    for msg in new_block:
        c = str(msg.get("content", ""))[:SUMMARY_FEED_MAX_CHARS] if msg.get("role") == "tool" else str(msg.get("content", ""))
        feed.append({**msg, "content": c})
    return await _extract_response_content(llm_agent, feed)