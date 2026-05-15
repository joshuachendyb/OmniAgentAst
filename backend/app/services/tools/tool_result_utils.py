# -*- coding: utf-8 -*-
"""
工具结果格式化公共函数 - 小沈 2026-05-15

原则：
  - 工具自己负责结果格式化（LLM数据+前端数据）
  - 共性截断/格式化逻辑抽到此模块复用
  - llm_data：精简关键字段给LLM决策
  - data：完整结构化数据给前端渲染
"""
import json
import logging

logger = logging.getLogger(__name__)

# 默认截断阈值
DEFAULT_MAX_OUTPUT_CHARS = 5000   # shell/code执行输出
DEFAULT_MAX_FILE_CHARS = 3000     # 文件内容
DEFAULT_MAX_BODY_CHARS = 2000     # HTTP响应体
DEFAULT_MAX_DOC_CHARS = 10000     # PDF/DOCX文档
DEFAULT_MAX_CLIPBOARD_CHARS = 5000
DEFAULT_MAX_ENV_VALUE_CHARS = 1000


def truncate_text(text: str, max_chars: int, suffix: str = None) -> tuple:
    """通用文本截断，返回(截断后文本, 是否截断) 小沈-2026-05-15"""
    if not text:
        return text, False
    if len(text) <= max_chars:
        return text, False
    tail = suffix or f"\n...[截断 {len(text) - max_chars} 字符]"
    return text[:max_chars] + tail, True


def format_output_for_llm(stdout: str, stderr: str, max_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> dict:
    """格式化命令/代码执行输出为llm_data 小沈-2026-05-15"""
    result = {}
    half = max_chars // 2
    if stdout:
        txt, tr = truncate_text(stdout, half)
        result["stdout"] = txt
        if tr:
            result["stdout_截断"] = f"原文{len(stdout)}字符"
    if stderr:
        txt, tr = truncate_text(stderr, half)
        result["stderr"] = txt
        if tr:
            result["stderr_截断"] = f"原文{len(stderr)}字符"
    return result if result else {"输出": "(无输出)"}


def format_file_content_llm(content: str, max_chars: int = DEFAULT_MAX_FILE_CHARS) -> dict:
    """格式化文件内容为llm_data 小沈-2026-05-15"""
    txt, tr = truncate_text(content, max_chars)
    result = {"内容": txt}
    if tr:
        result["原文长度"] = f"{len(content)}字符"
    result["行数"] = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
    return result


def make_json_safe(data, max_depth: int = 5, max_str_len: int = 500):
    """递归截断JSON数据防止超大dump 小沈-2026-05-15"""
    if max_depth <= 0:
        return "..."
    if isinstance(data, dict):
        return {k: make_json_safe(v, max_depth - 1, max_str_len) for k, v in data.items()}
    if isinstance(data, list):
        if len(data) > 100:
            return [make_json_safe(x, max_depth - 1, max_str_len) for x in data[:100]] + [f"...(共{len(data)}项)"]
        return [make_json_safe(x, max_depth - 1, max_str_len) for x in data]
    if isinstance(data, str) and len(data) > max_str_len:
        return data[:max_str_len] + f"...({len(data)}字符)"
    return data
