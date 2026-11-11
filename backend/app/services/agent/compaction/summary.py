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
# 2026-10-27 小欧 - 方案B: 往次摘要改为 assistant 消息注入(去 system 拼接); previousSummary 标签废弃, 与 summary_prompt.py 文案统一
# 2026-10-27 小欧 - _SUMMARY_TAIL_USER 文案润色: "以上"改"以下"并收紧表述, 与历史数据实际位置一致
# 2026-10-31 小欧 - 新增 _build_feed + estimate_feed_tokens: 原截断循环在两个摘要函数各写一份,
#   收口为单一截断口径; 门限判定改用它估"实际喂进去的体积"(tool content 按 feed_max 截断后),
#   治"拿未截断原文估→tool-heavy 历史虚报→误触发白裁旧轮" — 小欧-2026-10-31
# 2026-10-31 小欧 - estimate_feed_tokens docstring 声明"不含 SUMMARY_TEMPLATE/_SUMMARY_TAIL_USER 固定开销", 算法未动。— 小欧-2026-10-31
# 2026-11-01 小欧 - 七段重构(北京老陈亲定, 与 summary_prompt.py 同源): _SUMMARY_SECTIONS 改七段
#   (Goal→Previous Task Goal, Key Decisions→Task Plan and Decisions, 新增 Important Context 段, 顺序随模板定音);
#   _SUMMARY_TAIL_USER 文案「六段」→「七段」(语言保持中文不动, 10-07 实测背景在案) — 小欧-2026-11-01
# 2026-11-03 小欧 - log_and_print 增 level 参数: 摘要结构校验未过(丢弃用原历史)显式传 level="WARNING" — 小欧-2026-11-03
"""compaction.summary — C4: 锚定摘要压缩 + 增量块式锚定摘要(降本变体) — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 本文件仅承载「锚定/增量块摘要引擎」(调 LLM, 产出摘要文本, 不破坏原库)。
         触发/剪枝/装配/切分分别在 trigger.py / prune.py / assembler.py / split_turn.py。
依据: [4] 14.9.4② / 14.9.6 C5。
"""
import re
from typing import Dict, List, Optional

from app.config import (
    get_config,  # 小欧 2026-09-23 compaction配置化读 tuning.compaction.summary_feed_max_chars
)
from app.logger import (
    log_and_print,  # 2026-10-12 小欧 - 校验拒绝改 log-print（北京老陈令）: 只写日志文件则控制台无据可查 — 小欧-2026-10-12
)
from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE
from app.services.agent.compaction_constants import SUMMARY_FEED_MAX_CHARS
from app.services.agent.llm_call import (
    call_llm_text_task,  # 2026-10-20 16:2x 小欧 通用纯文本调用迁至 llm_call(SRP归位, 北京老陈裁定), 本模块改薄引用
)

# 摘要收尾指令(防"半截对话→续写", 见文件头编辑历史)
_SUMMARY_TAIL_USER = "以下是本次需要摘要的历史对话内容。请按 system 指定格式输出七段摘要。"


# 七段标记(与 SUMMARY_TEMPLATE 同源, 改模板即改此处) — 小欧 2026-10-12 / 2026-11-01 七段化
# 2026-10-25 小欧 段名去冒号(北京老陈令): Agents-A1 用 ## 段名 格式(无冒号), 原 "段名:" 子串匹配失败致摘要被误弃;
#   段名列表去冒号, 既供正则匹配, 也供子串兜底 — 小欧-2026-10-25
# 2026-10-26 小沈: 段名对齐 opencode 描述(Critical Context→Important Details, 删 Next Steps, 增 Summary), 与 summary_prompt.py 同源 — 小沈-2026-10-26
# 2026-11-01 小欧: 七段定音(北京老陈亲定): Goal→Previous Task Goal, Key Decisions→Task Plan and Decisions, 新增 Important Context, 顺序随模板 — 小欧-2026-11-01
_SUMMARY_SECTIONS = ("Previous Task Goal", "Task Plan and Decisions", "Important Details",
                     "Progress", "Summary", "Important Context", "Relevant Files")
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
    """七段标记是否齐全 — 2026-10-25 小欧 双重校验(北京老陈令)

    方法1(正则): 精确匹配段名, 容忍 ## 段名 / 段名: / **段名:** 三种形式;
    方法2(子串): 正则未全中时, 退化为段名子串查(最宽松, 段名本身出现即算);
    任一方法找全七段即通过。"""
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
    ①长度下限（太短必是垃圾）；②七段标记齐全（正则+子串双重, 容忍 ##/段名:/**段名:** 变体）；
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
        log_and_print(f"[compaction.summary] 摘要结构校验未过({reason})，丢弃用原历史", level="WARNING")
        return ""
    return t


def _build_feed(messages: List[Dict], feed_max: int) -> List[Dict]:
    """按「喂摘要 LLM」的截断口径复制消息: 仅 tool 的 content 截到 feed_max — 小欧 2026-10-31

    适用场景: 两个摘要函数构造 feed + estimate_feed_tokens 估请求体积, 三处同一截断口径。
    使用方法: 传消息列表 + 单条 tool 截断上限, 返回新列表(元素浅拷贝, 不改入参)。
    输入: messages 消息列表; feed_max 单条 tool content 的字符上限。
    输出: List[Dict] —— tool 的 content 截断, 其余角色 content 归一为 str(空值→空串)。
    关联逻辑: 原截断循环在 generate_anchored_summary / generate_chunked_summary 各写一份(同规则),
      现收口此处(DRY); 门限判定必须同口径, 否则原文估大→误判超窗→白裁早段轮次。
    """
    out: List[Dict] = []
    for msg in messages:
        c = str(msg.get("content", ""))
        if msg.get("role") == "tool":
            c = c[:feed_max]
        out.append({**msg, "content": c})
    return out


def estimate_feed_tokens(messages: List[Dict],
                         feed_max: Optional[int] = None) -> int:
    """摘要请求的真实体积(token): 按喂 LLM 的截断口径估算 — 小欧 2026-10-31

    适用场景: start 两条压缩路径进入阶梯裁剪前的门限判定(替代"拿未截断原文估"的旧口径)。
    使用方法: 传消息列表, 返回该列表喂给摘要 LLM 时的 token 估算。
    输入: messages 消息列表; feed_max 缺省读 tuning.compaction.summary_feed_max_chars。
    输出: int —— _build_feed 后的 token 估算(复用 MessageBuilder._estimate_tokens 单点)。
    前置条件: 无。
    口径边界: 不含 SUMMARY_TEMPLATE/_SUMMARY_TAIL_USER 固定开销(保守偏差, 判定略偏低→略晚触发)。 — 小欧-2026-10-31
    关联逻辑: 与 generate_* 的构造口径同源; tool 输出占历史体积九成以上(实测 93.86%),
      原文估会远超 feed, 用原文做门限必虚报 → 误触发 → 白丢早段轮次。
    """
    from app.services.agent.message_builder import MessageBuilder  # 局部 import 防循环
    if feed_max is None:
        feed_max = int(get_config().get('tuning.compaction.summary_feed_max_chars',
                                        SUMMARY_FEED_MAX_CHARS))
    return MessageBuilder._estimate_tokens(_build_feed(messages, feed_max))


async def generate_anchored_summary(llm_agent, messages: List[Dict]) -> str:
    """一次 LLM 调用产出锚定摘要 — 小欧 2026-08-16

    适用场景: C4 锚定摘要压缩(当前唯一接入主链路); 长任务跨多轮/续聊需保决策链, 且已放开 R4 零 LLM 原则。
    使用方法: 由 react_cycle._compact_injected_history await 调用(传 agent + 对话历史); 也可独立对任意消息列表调用。
    输入: llm_agent Agent 对象(须含 .llm_client, 用于发起流式调用); messages 对话消息列表。
    输出: str 锚定摘要文本(SUMMARY_TEMPLATE 七段 Markdown); 为空表示未产出(上层原样保留历史, 零退化)。
    前置条件: 由 react_cycle._compact_injected_history await 调用(仅在 start 超窗判定后), 不放宽安全门;
              tools=None 走 Text 模式不触发工具; 首参必须是 agent 对象而非 llm_client
    """
    feed: List[Dict] = []
    _feed_max = int(get_config().get('tuning.compaction.summary_feed_max_chars', SUMMARY_FEED_MAX_CHARS))  # 小欧 2026-09-23 compaction配置化
    # 2026-10-31 小欧: 截断循环收口 _build_feed(与增量函数/门限估算同一口径) — 小欧-2026-10-31
    feed = _build_feed(messages, _feed_max)
    feed = [{"role": "system", "content": SUMMARY_TEMPLATE}, *feed, {"role": "user", "content": _SUMMARY_TAIL_USER}]
    _src_len = sum(len(str(m.get("content") or "")) for m in messages)
    return _valid_summary_or_empty(await call_llm_text_task(llm_agent, feed), _src_len)


async def generate_chunked_summary(llm_agent, new_block: List[Dict],
                                   previous_summary: Optional[str] = None) -> str:
    """只把新增块喂 LLM, 与 [往次摘要] 合并 — 小欧 2026-08-16

    适用场景: C4 降本变体(备选); 长任务且会多次压缩时, 只摘要"新增块"避免全量重算, 成本随压缩次数线性。
    使用方法: 传 llm_agent + 新增块消息列表 + 可选上一轮摘要, await 返回摘要文本。
    输入: llm_agent Agent 对象(含 .llm_client); new_block 新增块消息列表(上次 compact 之后的新轮次);
          previous_summary 可选上一轮摘要。
    输出: str 增量合并后的摘要文本。
    前置条件: 同 generate_anchored_summary(须放开 R4、首参 agent 对象); 与 C4 区别仅在不重喂全量历史,
          只 new_block(tool 输出截断 2000) + [往次摘要]。
    """
    feed: List[Dict] = [{"role": "system", "content": SUMMARY_TEMPLATE}]
    if previous_summary:
        feed.append({"role": "assistant", "content": f"[往次摘要]: {previous_summary}"})
    _feed_max2 = int(get_config().get('tuning.compaction.summary_feed_max_chars', SUMMARY_FEED_MAX_CHARS))  # 小欧 2026-09-23 compaction配置化
    # 2026-10-31 小欧: 截断循环收口 _build_feed(与全量函数/门限估算同一口径) — 小欧-2026-10-31
    feed += _build_feed(new_block, _feed_max2)
    feed.append({"role": "user", "content": _SUMMARY_TAIL_USER})
    _src_len = sum(len(str(m.get("content") or "")) for m in new_block)
    if previous_summary:
        _src_len += len(previous_summary)
    return _valid_summary_or_empty(await call_llm_text_task(llm_agent, feed), _src_len)
