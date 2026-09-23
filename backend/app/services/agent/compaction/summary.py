# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: C4 锚定摘要引擎(一次 LLM, 喂截断输出, 原库完整)
#   2026-08-17 小健 修正: 原伪代码 `call_llm_with_fallback(agent=llm_client,...)` 参数错、`str(getattr(data,...))`
#                       取不到文本。真实协议(llm_stream.py:265)为 async generator 产 ("response", resp) tuple,
#                       文本在 resp["content"]; 首参是 agent 对象(含 .llm_client)。按真实协议重写。
#   2026-08-17 小健 新增: generate_chunked_summary + _extract_response_content(C4 降本变体, 复用统一提取)
#   2026-08-17 小健 补全: 各函数 docstring 补全适用场景/使用方法/前置条件/输入输出(043ed9c54)
#   2026-08-17 小健 常量归属迁移(北京老陈驱动): 压缩/裁剪常量权威迁至 agent 层根 compaction_constants.py, 本模块导入路径由 compaction.compaction_constants 改为 app.services.agent.compaction_constants
#   2026-08-17 小健 注释纠偏(北京老陈 2026-08-17): 前置条件去掉「须放开 R4(COMPACTION_ENABLED=True)」表述——开关仅限 start 超窗判定使用, 本摘要函数由 react_cycle._compact_injected_history 在超窗判定后 await 调用
#   2026-09-06 小欧 路径2-5E(文档[6]2.5.5②): _extract_response_content 判别由 ("response",dict) tuple 改
#                 StreamChunk.payload 单协议(与 react_step 同款); docstring 同步"真实协议"描述 — 小欧-2026-09-06
#   2026-09-23 小欧 compaction配置化: 两摘要函数 tool 截断读 tuning.compaction.summary_feed_max_chars 兜底 SUMMARY_FEED_MAX_CHARS
"""compaction.summary — C4: 锚定摘要压缩 + 增量块式锚定摘要(降本变体) — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 本文件仅承载「锚定/增量块摘要引擎」(调 LLM, 产出摘要文本, 不破坏原库)。
         触发/剪枝/装配/切分分别在 trigger.py / prune.py / assembler.py / split_turn.py。
依据: [4] 14.9.4② / 14.9.6 C5。
"""
from typing import List, Dict, Optional

from app.config import get_config  # 小欧 2026-09-23 compaction配置化读 tuning.compaction.summary_feed_max_chars
from app.services.agent.compaction_constants import SUMMARY_FEED_MAX_CHARS
from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE


async def _extract_response_content(llm_agent, feed: List[Dict]) -> str:
    """调 call_llm_with_fallback 并提取最终文本(路径2 StreamChunk 单协议) — 小健 2026-08-17; 2026-09-05 小健 协议升级 / 2026-09-06 小欧 落码

    真实协议(llm_call.py): call_llm_with_fallback(agent, messages, openai_tools) 为 async generator,
    item 为 StreamChunk, payload 非空且 type!=retrying 即终结响应, 文本在 payload["content"]
    (type="answer" 时=正文, type="error" 时=错误文案; type="action" 时无content键仅thought, 提取得空串——
    与改造前一致, 改造前 resp.get("content") 同样取不到, parity成立; 摘要有效输入仅answer/error)。
    """
    from app.services.agent.llm_call import call_llm_with_fallback  # 2026-09-05 小健 8.5拆分: llm_stream→llm_call改名

    content = ""
    async for item in call_llm_with_fallback(agent=llm_agent, messages=feed, openai_tools=None):
        _p = getattr(item, "payload", None)
        if _p is not None and isinstance(_p, dict) and _p.get("type") != "retrying":
            # 终结响应(answer/error 可取 content 键; action 无 content 键取空串, 与改造前 parity) — 小欧 2026-09-06
            c = str(_p.get("content") or "").strip()
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
    前置条件: 由 react_cycle._compact_injected_history await 调用(仅在 start 超窗判定后), 不放宽安全门;
              tools=None 走 Text 模式不触发工具; 首参必须是 agent 对象而非 llm_client
    """
    feed: List[Dict] = []
    _feed_max = int(get_config().get('tuning.compaction.summary_feed_max_chars', SUMMARY_FEED_MAX_CHARS))  # 小欧 2026-09-23 compaction配置化
    for msg in messages:
        if msg.get("role") == "tool":
            c = str(msg.get("content", ""))[:_feed_max]
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
    _feed_max2 = int(get_config().get('tuning.compaction.summary_feed_max_chars', SUMMARY_FEED_MAX_CHARS))  # 小欧 2026-09-23 compaction配置化
    for msg in new_block:
        c = str(msg.get("content", ""))[:_feed_max2] if msg.get("role") == "tool" else str(msg.get("content", ""))
        feed.append({**msg, "content": c})
    return await _extract_response_content(llm_agent, feed)