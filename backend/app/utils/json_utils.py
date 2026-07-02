# -*- coding: utf-8 -*-
"""
通用数据处理函数 — 小健 2026-05-28

【公共函数规范】
本文件是公共utility模块,所有数据处理相关公共函数必须在此定义。
禁止在业务代码(api/v1/、services/等)中重复定义公共函数。

【小沈 2026-05-28】新增:safe_parse_json
【小沈 2026-05-29】重命名:safe_parse_json → parse_json(符合命名规范)
【小沈 2026-05-30】移除:safe_truncate → 移至 agent/tool_result_formatter.py 内部(唯一消费者)
【小沈 2026-06-08】新增:raise_on_error参数，统一所有JSON解析场景
【小沈 2026-07-02】迁移:_try_fix_incomplete_json,_normalize_tool_params从base_service.py迁入(集中JSON解析函数)

Author: 小健 - 2026-05-28
"""

import ast
import json
from typing import Any, Dict, List, Optional


def parse_json(json_str: Optional[str], label: str = "", raise_on_error: bool = False) -> Any:
    """解析 JSON 字符串 — 小沈 2026-06-08 统一所有场景
    
    Args:
        json_str: JSON字符串
        label: 标签（用于日志）
        raise_on_error: True则抛异常，False则返回None
    
    Returns:
        解析结果或None（raise_on_error=False时）
    
    Raises:
        json.JSONDecodeError: raise_on_error=True且解析失败时
        TypeError: raise_on_error=True且传入None时
    """
    if not json_str:
        if raise_on_error:
            raise TypeError(f"{label}JSON字符串为空")
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        if raise_on_error:
            raise
        return None


def coerce_json(value: Any) -> Any:
    """若值为JSON字符串则解析为dict/list，否则原样返回 — 小健 2026-06-20
    
    LLM经常将dict/list参数序列化为JSON字符串传入，此函数自动反序列化。
    若字符串不是有效JSON，原样返回（可能是文件路径等合法字符串）。
    """
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    return value


def read_json_file(file_path: str, label: str = "", raise_on_error: bool = False) -> Any:
    """读取JSON文件 — 小沈 2026-06-17 新增公用函数
    
    Args:
        file_path: JSON文件路径
        label: 标签（用于日志）
        raise_on_error: True则抛异常，False则返回None
    
    Returns:
        解析结果或None（raise_on_error=False时）
    
    Raises:
        FileNotFoundError: raise_on_error=True且文件不存在时
        json.JSONDecodeError: raise_on_error=True且解析失败时
    """
    from pathlib import Path
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if raise_on_error:
            raise
        return None
    except json.JSONDecodeError:
        if raise_on_error:
            raise
        return None


def _try_fix_incomplete_json(json_str: str) -> Optional[Dict]:
    """
    尝试修复不完整/非标准JSON字符串 — 小沈 2026-07-02

    常见问题:
    1. 缺少右引号或右括号
    2. 反斜杠未转义
    3. 单引号Python dict格式(LLM受prompt中Python dict影响)

    返回: 解析成功的dict或None
    """
    if not json_str or not json_str.strip().startswith('{'):
        return None

    s = json_str.strip()

    # 第1步: ast.literal_eval处理Python dict格式(单引号/True/False/None等)
    try:
        result = ast.literal_eval(s)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError, MemoryError):
        pass

    # 第2步: 原有JSON修补策略(缺少括号/引号)
    fixes = [
        s,
        s + '"}',
        s + '}',
        s + '"',
        s.replace('\\\\', '\\') + '"}',
        s.replace('\\\\', '\\') + '}',
    ]

    for fixed in fixes:
        try:
            result = json.loads(fixed)
            # 补出 {} 但原始串无冒号 → 连 key 都没写过 → 空壳误修，跳过 — 小欧 2026-07-02
            if isinstance(result, dict) and len(result) == 0 and ":" not in s:
                continue
            return result
        except json.JSONDecodeError:
            continue

    return None


def _normalize_tool_params(params: Any) -> Any:
    """递归归一化tool params — 修复LLM双倍编码: 字符串形式的JSON array/object还
    原为真实类型. 在 json.loads(arguments)之后调用,对后续所有工具无感生效 - 小沈 2026-06-14"""
    if isinstance(params, dict):
        return {k: _normalize_tool_params(v) for k, v in params.items()}
    if isinstance(params, list):
        return [_normalize_tool_params(item) for item in params]
    if isinstance(params, str) and params.strip():
        s = params.strip()
        if s.startswith('[') or s.startswith('{'):
            try:
                parsed = json.loads(s)
                return _normalize_tool_params(parsed)
            except json.JSONDecodeError:
                pass
    return params


__all__ = [
    "parse_json",
    "coerce_json",
    "read_json_file",
    "_try_fix_incomplete_json",
    "_normalize_tool_params",
]
