# -*- coding: utf-8 -*-
"""
时间工具函数 — 统一时间戳/步骤计数器入口

【公共函数规范】
本文件是公共utility模块,所有时间相关公共函数必须在此定义。
禁止在业务代码(api/v1/、services/等)中重复定义公共函数。

【小健 2026-05-28】SRP+DRY:从chat_helpers.py提取集中到此
【小沈 2026-05-28】新增:convert_to_utc/ensure_ts_milliseconds/get_timestamp_ms/get_utc_timestamp
【小沈 2026-05-29】重命名:ensure_ts_milliseconds → ensure_timestamp_milliseconds(符合命名规范)

Author: 小健 - 2026-05-28
"""

# 编辑历史:
# 2026-07-14 - 小欧 - 修复ensure_timestamp_milliseconds: 13位epoch毫秒串被Python3.13宽松fromisoformat误解析为pre-1970 datetime致.timestamp()抛OSError[Errno22]; 数字串直接转int(判别毫秒/秒), 并对fromisoformat分支补充捕获OSError

from datetime import datetime, timezone
from typing import Any, Optional


def create_timestamp() -> int:
    """生成统一的时间戳(毫秒, UTC) — 小沈 2026-06-09 统一UTC"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def get_utc_timestamp() -> str:
    """获取UTC时间戳,ISO格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def convert_to_utc(time_value) -> str:
    """将时间转换为UTC ISO格式"""
    if not time_value:
        return get_utc_timestamp()
    if 'Z' in str(time_value) or '+' in str(time_value):
        return str(time_value)
    try:
        dt = datetime.fromisoformat(str(time_value).replace(' ', 'T'))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError):
        return get_utc_timestamp()


def ensure_timestamp_milliseconds(ts_value: Any) -> int:
    """确保时间戳转为毫秒整数

    小欧 2026-07-14 修复: 13位epoch毫秒串(如'1784031800406')被Python3.13宽松fromisoformat
    误解析为pre-1970的datetime(公元1784年), 调用.timestamp()时Windows mktime下限(1970)限制
    抛OSError[Errno22]; 原except仅捕获ValueError/TypeError/OverflowError漏掉OSError。
    修复: 数字串直接转int(判别毫秒/秒), 并对fromisoformat分支补充捕获OSError。
    """
    if isinstance(ts_value, (int, float)):
        return int(ts_value)
    if isinstance(ts_value, str):
        s = ts_value.strip()
        if s.lstrip('-').isdigit():
            try:
                val = int(s)
                # 13位及以上(>=1e12)视为毫秒, 否则视为秒
                return int(val) if val >= 1_000_000_000_000 else int(val * 1000)
            except (ValueError, OverflowError):
                pass
    try:
        return int(datetime.fromisoformat(str(ts_value).replace(' ', 'T')).timestamp() * 1000)
    except (ValueError, TypeError, OverflowError, OSError):
        return int(datetime.now(timezone.utc).timestamp() * 1000)


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间格式字符串,默认 YYYY-MM-DD HH:MM:SS

    消除 43 处散落的重复 datetime.now().strftime(...) 调用
    """
    return datetime.now().strftime(fmt)


def timestamp_for_filename() -> str:
    """生成文件名时间戳 YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_timestamp(val: Any) -> Optional[str]:
    """通用时间戳格式化 — 小沈 2026-02-17
    小欧 2026-07-04 修复: 增加OSError捕获，处理Windows不支持负时间戳的问题
    小欧 2026-07-10 M-19: 为None时返回None
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val / 1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
        except (OSError, OverflowError, ValueError):
            return str(val)
    if isinstance(val, str):
        return val.replace('+00:00', 'Z') if '+00:00' in val else (val + 'Z' if not val.endswith('Z') else val)
    return convert_to_utc(val)


__all__ = [
    "create_timestamp",
    "get_utc_timestamp",
    "convert_to_utc",
    "ensure_timestamp_milliseconds",
    "timestamp_for_filename",
    "now_str",
    "format_timestamp",
]
