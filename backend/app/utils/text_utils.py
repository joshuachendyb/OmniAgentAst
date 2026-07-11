# -*- coding: utf-8 -*-
"""
文本处理工具函数 — 小沈 2026-06-09

【公共函数规范】
本文件是公共utility模块,所有文本处理相关公共函数必须在此定义。
禁止在业务代码中重复定义公共函数。

Author: 小沈 - 2026-06-09
v2.0: 新增format_tool_call_markup — 小欧 2026-07-12
"""
import json
import re
from typing import Optional


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


def _format_xml_tool_block(match):
    """将<tool_call>...块格式化为纯文本 — 小欧 2026-07-12"""
    block = match.group(0)
    func_m = re.search(r'<function=([^>\n]+)>', block)
    func_name = func_m.group(1) if func_m else "unknown"
    params = []
    for pm in re.finditer(r'<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>', block, re.DOTALL):
        params.append(f"  {pm.group(1)}: {pm.group(2).strip()}")
    r = f"[工具调用] {func_name}"
    if params:
        r += "\n" + "\n".join(params)
    return r


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
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


__all__ = [
    "truncate_text",
    "smart_truncate_text",
    "add_line_numbers",
    "format_tool_call_markup",
]