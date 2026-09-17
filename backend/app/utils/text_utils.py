# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-06-09 - 小沈 - 新建: 文本处理公共工具
# 2026-07-12 - 小欧 - v2.0: 新增 format_tool_call_markup
# 2026-07-16 - 小欧 - v2.1: 新增 extract_tool_call_xml(P1-04推理降级XML提取) + _format_xml_tool_block改调它(DRY)
# 2026-08-20 - 小欧 - 遥测收敛: 本文件在遥测链路被引用(工具调用标记格式化), 本次无逻辑改动仅补标准编辑历史头
# 2026-08-30 - 小欧 - 13.11(设计文档[2]13.12.9): 新增公用 normalize_blank_lines(空行规约, 前后端同一张规则表, 幂等);
#   format_tool_call_markup 末尾 \n{3,} 压缩+strip 收敛至该公用函数(answer 轮行为逐字节等价, DRY); __all__ 登记
# 2026-09-05 小健 - answer_focus第二阶段搬一(8.1): 新增公用 dedup_repeat(从 answer_handler._dedup_repeat 去下划线转公有,
#   逐字复制含L97 logger.warning; 随迁REPEAT_*三常量与Counter/logger import) - 小健-2026-09-05
"""
文本处理工具函数 — 小沈 2026-06-09

【公共函数规范】
本文件是公共utility模块,所有文本处理相关公共函数必须在此定义。
禁止在业务代码中重复定义公共函数。

Author: 小沈 - 2026-06-09
v2.0: 新增format_tool_call_markup — 小欧 2026-07-12
v2.1: 新增extract_tool_call_xml(P1-04推理降级XML提取) + _format_xml_tool_block改调它(DRY) — 小欧 2026-07-16
"""
import json
import re
from collections import Counter
from typing import Optional, Dict, Any
from app.logger import logger


def truncate_text(text: str, max_chars: int, suffix: Optional[str] = None) -> tuple:
    """通用尾部截断,返回(截断后文本, 是否截断) — 小沈 2026-06-17 从tool_result_formatter迁入"""
    if not text:
        return text, False
    if len(text) <= max_chars:
        return text, False
    tail = suffix or f"\n...[截断 {len(text) - max_chars} 字符]"
    return text[:max_chars] + tail, True


def add_line_numbers(content: str, offset: int = 1) -> str:
    """给文本内容添加行号前缀 — 小欧 2026-07-05"""
    if not content:
        return content
    lines = content.rstrip("\n").split("\n")
    last_lineno = offset + len(lines) - 1
    width = len(str(last_lineno))
    return "\n".join(
        f"{offset + i:>{width}}|{line}"
        for i, line in enumerate(lines)
    )


def smart_truncate_text(content: str, budget: int, head_ratio: float = 0.6) -> str:
    """智能截断文本 — 小沈 2026-06-09 提取为公用函数
    
    Args:
        content: 待截断文本
        budget: 最大长度预算
        head_ratio: 头部比例（默认0.6）
    
    Returns:
        截断后的文本
    
    功能：
        - 保留头部和尾部，省略中间
        - 确保不超预算
        - 添加省略标记
    """
    if len(content) <= budget:
        return content
    
    OMISSION_TEXT_LEN = 50
    if budget <= OMISSION_TEXT_LEN + 10:
        return content[:budget]
    
    head_budget = int(budget * head_ratio)
    tail_budget = budget - head_budget - OMISSION_TEXT_LEN
    head = content[:head_budget]
    tail = content[-tail_budget:] if tail_budget > 0 else ""
    result = f"{head}\n... [中间省略 {len(content) - budget} 字符] ...\n{tail}"
    
    if len(result) > budget:
        result = result[:budget]
    
    return result


def _try_format_json_tool_call(obj):
    """若parsed JSON是tool call对象则返回格式化文本,否则None — 小欧 2026-07-12"""
    if not isinstance(obj, dict):
        return None
    if "function" in obj and isinstance(obj["function"], dict) and "name" in obj["function"]:
        name = obj["function"]["name"]
        args_raw = obj["function"].get("arguments", "{}")
        args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw if isinstance(args_raw, dict) else {})
        params = [f"  {k}: {v}" for k, v in args.items()]
        r = f"[工具调用] {name}"
        if params:
            r += "\n" + "\n".join(params)
        return r
    if "name" in obj and "arguments" in obj:
        args_raw = obj["arguments"]
        args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw if isinstance(args_raw, dict) else {})
        params = [f"  {k}: {v}" for k, v in args.items()]
        r = f"[工具调用] {obj['name']}"
        if params:
            r += "\n" + "\n".join(params)
        return r
    return None


def extract_tool_call_xml(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 <tool_call> XML 格式的工具调用 — 小欧 2026-07-16 (P1-04)

    解析 <tool_call><function=name><parameter=k>v</parameter></function></tool_call>
    返回 {"tool_name": str, "tool_params": Dict[str, str]}

    本函数是此 XML schema 的唯一解析源(DRY)。
    _format_xml_tool_block 调用本函数，正则定义不重复。
    """
    block_m = re.search(r'<tool_call>.*?</tool_call>', text, re.DOTALL)
    if not block_m:
        return None
    block = block_m.group(0)
    func_m = re.search(r'<function=([^>\n]+)>', block)
    if not func_m:
        return None
    tool_name = func_m.group(1)
    tool_params = {}
    for pm in re.finditer(r'<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>', block, re.DOTALL):
        tool_params[pm.group(1)] = pm.group(2).strip()
    return {"tool_name": tool_name, "tool_params": tool_params}


def _format_xml_tool_block(match):
    """将<tool_call>...块格式化为纯文本 — 小欧 2026-07-12; 小欧 2026-07-16 改调extract_tool_call_xml(DRY)"""
    block = match.group(0)
    extracted = extract_tool_call_xml(block)
    if not extracted:
        return "[工具调用] unknown"
    params = [f"  {k}: {v}" for k, v in extracted["tool_params"].items()]
    r = f"[工具调用] {extracted['tool_name']}"
    return r + "\n" + "\n".join(params) if params else r


# 2026-08-30 小欧 13.11: 空行规约公用函数(后端落库收口入口) — 与前端 normalizeBlankLines 同一张规则表(幂等)
def normalize_blank_lines(text: str) -> str:
    """空行规约——至多保留一个段落空行(13.11 规则表): 连续空行(含整行仅空格/制表)折叠为
    一个空行(逐行折叠, KISS 幂等), 段首尾 trim. — 小欧 2026-08-30"""
    if not text:
        return text
    out = []
    blank = 0
    for _ln in text.split("\n"):
        if not _ln.strip():
            blank += 1
            if blank == 1:
                out.append("")
        else:
            blank = 0
            out.append(_ln)
    return "\n".join(out).strip()


def format_tool_call_markup(text: str) -> str:
    """将LLM输出中的XML/JSON tool call标记格式化为纯文本

    处理格式:
      - Anthropic XML: <tool_call><function=name><parameter=k>v</parameter></function></tool_call>
      - OpenAI JSON:  {"function": {"name": "...", "arguments": "..."}}

    Args:
        text: 原始LLM输出文本(string不限制)

    Returns:
        格式化后的纯文本(带换行,无XML/JSON标记)
    """
    if not text:
        return text

    text = re.sub(r'<tool_call>.*?</tool_call>', _format_xml_tool_block, text, flags=re.DOTALL)

    result = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 1
            j = i + 1
            while j < len(text) and depth > 0:
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                j += 1
            if depth == 0:
                candidate = text[i:j]
                try:
                    obj = json.loads(candidate)
                    formatted = _try_format_json_tool_call(obj)
                    if formatted:
                        result.append(formatted)
                        i = j
                        continue
                except json.JSONDecodeError:
                    pass
        result.append(text[i])
        i += 1

    text = "".join(result)
    # 13.11 收口: 原 \n{3,} 压缩+strip 收敛至公用 normalize_blank_lines(行为逐字节等价, DRY) — 小欧 2026-08-30
    return normalize_blank_lines(text)


# ── 重复检测(版本2026-07-17: 句子频率法替代固定chunk) ── 小健 2026-09-05: 从 answer_handler.py 迁入
REPEAT_CHECK_MIN_LEN = 250     # 小健 2026-09-05：从 answer_handler.py:58 迁移，逐字（启动门槛: 不足250字不检）
SENTENCE_MIN_REPEAT = 3        # 小健 2026-09-05：从 answer_handler.py:59 迁移，逐字（同一句≥3次标记重复）
DUP_RATIO = 0.5                # 小健 2026-09-05：从 answer_handler.py:60 迁移，逐字（占比过半才截断）


def dedup_repeat(content: str) -> str:
    """【卡顿循环重复去重】基于句子频率, 非通用去重工具
    【设计意图】LLM陷入卡顿循环时(如A-B交替/简单块重复), 剔除原样重复句子, 保留首次有效内容
    【防误伤边界】① 长度<REPEAT_CHECK_MIN_LEN 不检测; ② 句子数<10不检测;
        ③ 排除markdown表行(行首|); ④ 重复占比>DUP_RATIO才截断; ⑤ 仅精确句子匹配, 非语义相似
    【调用前提】content 为 final/推理文本; 返回截断后文本"""
    if len(content) < REPEAT_CHECK_MIN_LEN:
        return content
    parts = re.split(r'(?<=[。\n])', content)
    parts = [p for p in parts if len(p.strip()) > 0]
    if len(parts) < 10:
        return content
    counter = Counter(parts)
    repeated = {s for s, cnt in counter.items()
                if cnt >= SENTENCE_MIN_REPEAT
                and not s.strip().startswith('|')}
    if not repeated:
        return content
    result = []
    seen = set()
    for p in parts:
        if p in repeated and p in seen:
            continue
        if p in repeated:
            seen.add(p)
        result.append(p)
    deduped = "".join(result)
    if len(deduped) >= len(content):
        return content
    ratio = 1 - len(deduped) / len(content)
    if ratio < DUP_RATIO:
        return content
    logger.warning(f"[L1-C2b] 检测到无意义重复(final {len(content)}字, 重复占比 {ratio:.0%}), 已去重截断")
    return deduped


def truncate_summary(detail: str, max_chars: int = 200) -> str:
    """取 detail 首行作为简短摘要 — 小欧 2026-07-24(由document系列工具引用补回)

    语义: 错误/警告摘要应嵌入 detail 的首行, 避免全文拖垮 summary。
    若首行为空则退化为 smart_truncate_text 摘要; 超长则截断。
    """
    if not detail:
        return ""
    first_line = detail.strip().splitlines()[0].strip() if detail.strip() else ""
    if len(first_line) <= max_chars:
        return first_line
    return first_line[:max_chars - 3] + "..."


__all__ = [
    "truncate_text",
    "smart_truncate_text",
    "add_line_numbers",
    "extract_tool_call_xml",
    "normalize_blank_lines",
    "format_tool_call_markup",
    "truncate_summary",
    "dedup_repeat",
]
