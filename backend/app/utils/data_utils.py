# -*- coding: utf-8 -*-
"""
通用数据处理函数 — 小健 2026-05-28

【公共函数规范】
本文件是公共utility模块，所有数据处理相关公共函数必须在此定义。
禁止在业务代码（api/v1/、services/等）中重复定义公共函数。

【小沈 2026-05-28】新增：safe_parse_json
【小沈 2026-05-29】重命名：safe_parse_json → parse_json（符合命名规范）
【小沈 2026-05-30】移除：safe_truncate → 移至 agent/tool_result_formatter.py 内部（唯一消费者）

Author: 小健 - 2026-05-28
"""

import json
from typing import Any, Optional


def parse_json(json_str: Optional[str], label: str = "") -> Any:
    """解析 JSON 字符串，失败返回 None"""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


__all__ = [
    "parse_json",
]
