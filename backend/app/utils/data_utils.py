# -*- coding: utf-8 -*-
"""
通用数据处理函数 — 小健 2026-05-28

DRY：从 tool_result_utils.py 提取集中于此，避免 agent 层跨层导入 tools 层。

Author: 小健 - 2026-05-28
"""

from typing import Any


def safe_truncate(data: Any, limit: int) -> Any:
    """安全截断：仅防 json.dumps OOM，非业务截断 — 小沈 2026-05-27

    供 tool_result_formatter.py 和任何需要安全兜底截断的地方复用。

    Args:
        data: 待截断数据（dict/list/其他）
        limit: 条目数量上限

    Returns:
        截断后的数据
    """
    if isinstance(data, dict):
        if len(data) > limit:
            keys = list(data.keys())[:limit]
            return {k: data[k] for k in keys}
    elif isinstance(data, list):
        if len(data) > limit:
            return data[:limit]
    return data


__all__ = [
    "safe_truncate",
]
