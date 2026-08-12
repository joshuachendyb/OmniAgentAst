
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #19 fix: convert_to_utc(None)返回None而非当前时间
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
# 2026-07-18 - 小欧 - #19 fix: convert_to_utc(None) 返回 None 而非当前时间, 返回值类型改为 Optional[str]; 调用方 grep 确认均不受影响
# 2026-07-26 - 小沈 - 欧阳报告: 新增safe_utc_offset安全获取本地UTC偏移(utcoffset()可能返回None)
# 2026-08-08 - 小欧 - 全程统一本地时区(task004问题1): 新增get_local_iso_timestamp/to_local_iso; format_timestamp改语义(字符串不再强制加Z, 走to_local_iso); __all__补2项

from datetime import datetime, timezone
from typing import Any, Optional


def create_timestamp() -> int:
    """生成统一的时间戳(毫秒, UTC) — 小沈 2026-06-09 统一UTC"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def get_utc_timestamp() -> str:
    """获取UTC时间戳,ISO格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_local_iso_timestamp() -> str:
    """获取本地时间戳,ISO格式(无Z/无时区偏移) — 小欧 2026-08-08

    全程统一本地时间(task004报告问题1): 与get_utc_timestamp()(UTC)对应,
    返回本地时区ISO格式(如 2026-08-08T16:52:34.123456)。
    前端 Date.parse 对 T 分隔ISO解析按本地时区, 展示正确;
    若含Z则按UTC解析会差8小时, 故本地时间禁止带Z/偏移后缀。
    """
    return datetime.now().isoformat()


def to_local_iso(time_value: Any) -> Optional[str]:
    """任意时间值 → 本地ISO(无Z/无偏移) — 小欧 2026-08-08

    支持: None→None; datetime(aware/naive)→本地; int/float(毫秒)→本地;
          str(含Z/+00:00/+08:00等任意偏移/naive)→本地。解析失败原样返回。
    用于: database.py 参数归一化、迁移脚本、输出层。
    """
    if time_value is None:
        return None
    # datetime 类型 (aware → 本地, naive → 原样)
    if isinstance(time_value, datetime):
        if time_value.tzinfo is not None:
            time_value = time_value.astimezone()
        return time_value.replace(tzinfo=None).isoformat()
    # int/float 毫秒
    if isinstance(time_value, (int, float)):
        try:
            return datetime.fromtimestamp(time_value / 1000).isoformat()
        except (OSError, OverflowError, ValueError):
            return str(time_value)
    # 字符串: 统一 fromisoformat 解析(原生支持 Z/偏移), 成功则转本地去偏移, 失败原样返回
    s = str(time_value).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))  # 兼容裸Z(Python<3.13)
        if dt.tzinfo is not None:
            dt = dt.astimezone()  # 任意时区 → 本地
        return dt.replace(tzinfo=None).isoformat()  # 去偏移
    except (ValueError, TypeError, OverflowError):
        return s  # 解析失败原样返回


def convert_to_utc(time_value) -> Optional[str]:
    """将时间转换为UTC ISO格式；None 如实返回 None — 小欧 2026-07-18 #19 fix"""
    if time_value is None:
        return None
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
    """通用时间戳格式化(本地时区) — 小沈 2026-02-17
    小欧 2026-07-04 修复: 增加OSError捕获，处理Windows不支持负时间戳的问题
    小欧 2026-07-10 M-19: 为None时返回None
    小欧 2026-08-08 全程统一本地: 字符串不再强制追加Z, 走 to_local_iso 统一转换
    """
    if val is None:
        return None
    return to_local_iso(val)


def safe_utc_offset() -> int:
    """安全获取本地UTC偏移小时数 — 小沈 2026-07-26

    datetime.now().astimezone().utcoffset() 在某些环境返回None(欧阳报告),
    此时默认UTC+8。"""
    try:
        offset = datetime.now().astimezone().utcoffset()
        if offset is None:
            return 8
        return int(offset.total_seconds() / 3600)
    except (OSError, AttributeError, TypeError):
        return 8


__all__ = [
    "create_timestamp",
    "get_utc_timestamp",
    "get_local_iso_timestamp",  # 小欧 2026-08-08 全程统一本地时区新增
    "to_local_iso",             # 小欧 2026-08-08 全程统一本地时区新增
    "convert_to_utc",
    "ensure_timestamp_milliseconds",
    "timestamp_for_filename",
    "now_str",
    "format_timestamp",
    "safe_utc_offset",
]

