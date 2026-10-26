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
#   2026-09-06 小欧 路径2-5E(文档落码): _extract_response_content 判别由 ("response",dict) tuple 改
#                 StreamChunk.payload 单协议(与 react_step 同款); docstring 同步"真实协议"描述 — 小欧-2026-09-06
# 2026-09-23 小欧 compaction配置化: 两摘要函数 tool 截断读 tuning.compaction.summary_feed_max_chars 兜底 SUMMARY_FEED_MAX_CHARS
# 2026-10-07 北京老陈 新增 _SUMMARY_TAIL_USER 收尾指令: 注入历史末条是 assistant, 摘要 feed 以 assistant
#   收尾构成半截对话 → 模型按对话补全续写而非汇总(实测六段命中率 16%); 末条补 user 请求后 6/6=100%。
#   两摘要函数均适用(generate_chunked_summary 同理)。
# 2026-10-10 小欧 摘要只取 type=="answer": error 的 content 是错误文案, 收下会让上层拿它顶替历史注入、历史全丢。
# 2026-10-12 小欧 新增 _valid_summary_or_empty 单函数校验(北京老陈令): 长度下限+六段齐全+拒绝开头+压缩比,
#   任一不过返空串走零退化; 两摘要函数共用, 不改流程 — 小欧-2026-10-12
# 2026-10-20 15:45 小欧 北京老陈令: 私有 _extract_response_content 升格为公用函数 call_llm_text_task(纯改名不改逻辑),
#   供 fetchpage prompt 提取等工具场景复用 — 通道(callTextForTask 适配钩子 + call_llm_with_fallback 兜底)不变,
#   任何 provider/model 通用; 两摘要函数调用点同步更名, 零行为变化
# 2026-10-20 16:2x 小欧 北京老陈裁定: 通用纯文本调用寄宿压缩摘要引擎不合SRP, call_llm_text_task 函数体
#   原样迁至 app/services/agent/llm_call.py(全系统"发起LLM调用"唯一入口层), 本模块改顶部薄引用,
#   两摘要函数调用点代码零变化(名字同名直用); 文档: FUNCTIONS.md §3.5→§3.7 登记同步迁移
# 2026-10-25 小欧 段标记校验放宽(北京老陈令): Agents-A1 用 ## 段名 格式(无冒号), 原 "段名:" 子串匹配
#   失败致摘要被误弃→零退化回退原历史超窗→上游400; 改双重校验: ①段名去冒号子串匹配 ②正则容忍 ##/段名:/**段名:**
#   三种形式; 六段全中即过 — 小欧-2026-10-25
# 2026-10-26 小沈 - _SUMMARY_SECTIONS 段名同步(与 summary_prompt.py 模板同源): Critical Context→Important Details, 删 Next Steps, 增 Summary, Progress 保留; 段名变更必同步此处, 否则校验恒判"缺段标记"→摘要被弃→压缩失效 — 小沈-2026-10-26
"""compaction.summary — C4: 锚定摘要压缩 + 增量块式锚定摘要(降本变体) — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 本文件仅承载「锚定/增量块摘要引擎」(调 LLM, 产出摘要文本, 不破坏原库)。
         触发/剪枝/装配/切分分别在 trigger.py / prune.py / assembler.py / split_turn.py。
依据: [4] 14.9.4② / 14.9.6 C5。
"""
import re

from typing import List, Dict, Optional

from app.config import get_config  # 小欧 2026-09-23 compaction配置化读 tuning.compaction.summary_feed_max_chars
from app.logger import logger, log_and_print  # 2026-10-12 小欧 - 校验拒绝改 log-print（北京老陈令）: 只写日志文件则控制台无据可查；logger 保留供 L56 老分支 — 小欧-2026-10-12
from app.services.agent.compaction_constants import SUMMARY_FEED_MAX_CHARS
from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE
from app.services.agent.llm_call import call_llm_text_task  # 2026-10-20 16:2x 小欧 通用纯文本调用迁至 llm_call(SRP归位, 北京老陈裁定), 本模块改薄引用

# 摘要收尾指令(防"半截对话→续写", 见文件头编辑历史)
_SUMMARY_TAIL_USER = "以上是历史对话数据。请按 system 指定格式输出六段摘要。"


# 六段标记(与 SUMMARY_TEMPLATE 同源, 改模板即改此处) — 小欧 2026-10-12
# 2026-10-25 小欧 段名去冒号(北京老陈令): Agents-A1 用 ## 段名 格式(无冒号), 原 "段名:" 子串匹配失败致摘要被误弃;
#   段名列表去冒号, 既供正则匹配, 也供子串兜底 — 小欧-2026-10-25
# 2026-10-26 小沈: 段名对齐 opencode 描述(Critical Context→Important Details, 删 Next Steps, 增 Summary), 与 summary_prompt.py 同源 — 小沈-2026-10-26
_SUMMARY_SECTIONS = ("Goal", "Key Decisions", "Important Details",
                     "Progress", "Summary", "Relevant Files")
_SUMMARY_MIN_CHARS = 200  # 缺省; 优先读 tuning.compaction.summary_min_chars（与本文件配置化口径一致）
_REFUSAL_PREFIXES = ("抱歉", "对不起", "很抱歉")

# 2026-10-25 小欧 段标记正则(北京老陈令): 容忍三种段名形式 — ## 段名 / 段名: / **段名:** ;
#   前缀容忍 #{1,6} / - / ** , 段名后跟(:/换行/行尾)零宽断言; 与去冒号子串兜底双重保险 — 小欧-2026-10-25
_SECTION_RE = re.compile(
    r'(?:^|\n)\s*'                                      # 行首/换行后 + 可选空白
    r'(?:#{1,6}\s+|-\s+)?'                             # 可选前缀: ##/###/-
    r'\**\s*'                                            # 可选 ** 前缀(加粗)
    r'(' + '|'.join(re.escape(s) for s in _SUMMARY_SECTIONS) + r')'
    r'\s*\**\s*'                                        # 可选 ** 后缀
    r'(?=[:]|\n|$)',                                    # 后跟(:/换行/行尾), 零宽断言
    re.IGNORECASE
)


def _sections_complete(t: str) -> bool:
    """六段标记是否齐全 — 2026-10-25 小欧 双重校验(北京老陈令)

    方法1(正则): 精确匹配段名, 容忍 ## 段名 / 段名: / **段名:** 三种形式;
    方法2(子串): 正则未全中时, 退化为段名子串查(最宽松, 段名本身出现即算);
    任一方法找全六段即通过。"""
    # 方法1: 正则匹配
    found = {m.group(1).lower() for m in _SECTION_RE.finditer(t)}
    if found == {s.lower() for s in _SUMMARY_SECTIONS}:
        return True
    # 方法2: 段名子串兜底(最宽松)
    tl = t.lower()
    return all(s.lower() in tl for s in _SUMMARY_SECTIONS)


def _valid_summary_or_empty(text: str, src_len: int = 0) -> str:
    """摘要结构校验（单函数，两摘要函数共用）— 小欧 2026-10-12

    任一不过返空串，调用方走现有零退化路径（装配原历史），不改流程：
    ①长度下限（太短必是垃圾）；②六段标记齐全（正则+子串双重, 容忍 ##/段名:/**段名:** 变体）；
    ③拒绝话术开头（只认开头，避正文误伤）；④不比原文长（没压反而胀）。
    """
    t = (text or "").strip()
    reason = ""
    _min = int(get_config().get('tuning.compaction.summary_min_chars', _SUMMARY_MIN_CHARS))
    if not t:
        reason = "空响应"
    elif len(t) < _min:
        reason = f"过短({len(t)}字<{_min}字)"
    elif not _sections_complete(t):
        reason = "缺段标记"
    elif t.startswith(_REFUSAL_PREFIXES):
        reason = "拒绝话术开头"
    elif src_len > 0 and len(t) >= src_len:
        reason = f"未压缩({len(t)}字>=原文{src_len}字)"
    if reason:
        log_and_print(f"[compaction.summary] 摘要结构校验未过({reason})，丢弃用原历史")
        return ""
    return t


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
    feed = [{"role": "system", "content": prompt}, *feed, {"role": "user", "content": _SUMMARY_TAIL_USER}]
    _src_len = sum(len(str(m.get("content") or "")) for m in messages)
    return _valid_summary_or_empty(await call_llm_text_task(llm_agent, feed), _src_len)


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
    feed.append({"role": "user", "content": _SUMMARY_TAIL_USER})
    _src_len = sum(len(str(m.get("content") or "")) for m in new_block)
    if previous_summary:
        _src_len += len(previous_summary)
    return _valid_summary_or_empty(await call_llm_text_task(llm_agent, feed), _src_len)