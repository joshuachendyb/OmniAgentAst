# -*- coding: utf-8 -*-
"""
工具结果格式化公共函数 - 小沈 2026-05-15

原则：
  - 工具自己负责结果格式化（LLM数据+前端数据）
  - 共性截断/格式化逻辑抽到此模块复用
  - llm_data：≤阈值全给，超阈值截断但保留关键结构
  - data：完整结构化数据给前端渲染
"""
import json
import logging

logger = logging.getLogger(__name__)

# 【修复 小健 2026-05-16】统一阈值原则：≤5K全给不截断，超5K才截断
DEFAULT_MAX_OUTPUT_CHARS = 5000   # shell/code执行输出（stdout+stderr合计）
DEFAULT_MAX_FILE_CHARS = 8000     # 文件内容（代码文件常需完整内容才能修改）
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
    """格式化命令/代码执行输出为llm_data 小沈-2026-05-15
    【修复 小健 2026-05-16】不再对半砍stdout/stderr，按实际大小分配额度"""
    result = {}
    stdout_len = len(stdout) if stdout else 0
    stderr_len = len(stderr) if stderr else 0
    total_len = stdout_len + stderr_len

    # 总量不超限，全给
    if total_len <= max_chars:
        if stdout:
            result["stdout"] = stdout
        if stderr:
            result["stderr"] = stderr
    else:
        # 按实际大小比例分配额度，至少给1K
        if stdout_len > 0:
            stdout_budget = max(1000, int(max_chars * stdout_len / total_len))
            txt, tr = truncate_text(stdout, stdout_budget)
            result["stdout"] = txt
            if tr:
                result["stdout_截断"] = f"原文{stdout_len}字符"
        if stderr_len > 0:
            stderr_budget = max(1000, int(max_chars * stderr_len / total_len))
            txt, tr = truncate_text(stderr, stderr_budget)
            result["stderr"] = txt
            if tr:
                result["stderr_截断"] = f"原文{stderr_len}字符"
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


def build_next_actions(actions: list) -> list:
    """构建next_actions列表，§11.3 P15返回值自解释规范 小沈-2026-05-19

    每个action格式: (tool, description, when[, params])
    - tool: 推荐调用的工具名(str)
    - description: 人类可读说明(str)
    - when: 触发条件(str)
    - params: 建议参数(dict, 可选)

    用法:
        na = build_next_actions([
            ("analyze_data", "对这些数据进行统计分析", "需要统计平均值、最大值、最小值时"),
            ("filter_data", "筛选特定条件的数据", "需要按条件过滤时", {"column": "age"}),
        ])
        return {"code": "SUCCESS", "data": {...}, "message": "...", "next_actions": na}
    """
    result = []
    for item in actions:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        entry = {
            "tool": item[0],
            "description": item[1],
            "when": item[2],
        }
        if len(item) >= 4 and isinstance(item[3], dict):
            entry["params"] = item[3]
        result.append(entry)
    return result
