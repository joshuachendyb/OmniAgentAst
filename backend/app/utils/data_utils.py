# -*- coding: utf-8 -*-
"""
通用数据处理函数 — 小健 2026-05-28

【公共函数规范】
本文件是公共utility模块，所有数据处理相关公共函数必须在此定义。
禁止在业务代码（api/v1/、services/等）中重复定义公共函数。

DRY：从 tool_result_utils.py 提取集中于此，避免 agent 层跨层导入 tools 层。

【小沈 2026-05-28】新增：safe_parse_json
【小沈 2026-05-29】重命名：safe_parse_json → parse_json（符合命名规范）

Author: 小健 - 2026-05-28
"""

import json
from typing import Any, Optional


def safe_truncate(data: Any, limit: int) -> Any:
    """安全截断：仅防 json.dumps OOM，非业务截断 — 小沈 2026-05-27"""
    if isinstance(data, dict):
        if len(data) > limit:
            keys = list(data.keys())[:limit]
            return {k: data[k] for k in keys}
    elif isinstance(data, list):
        if len(data) > limit:
            return data[:limit]
    return data


def parse_json(json_str: Optional[str], label: str = "") -> Any:
    """解析 JSON 字符串，失败返回 None"""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


__all__ = [
    "safe_truncate",
    "parse_json",
]
