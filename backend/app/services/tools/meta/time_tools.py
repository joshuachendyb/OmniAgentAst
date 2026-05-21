# -*- coding: utf-8 -*-
"""
时间工具函数模块 - 为普通用户提供时间相关功能

【迁移说明】2026-04-26 小沈
- 本文件从 app/tools/time_tools.py 迁移而来

【2026-05-02 小沈重构】
- 移除所有 @register_tool 装饰器，注册由 time_register.py 显式完成
- 移除 register_tool/ToolCategory 导入
- 移除 Pydantic 模型导入（模型由 time_register.py 导入）

【2026-05-18 小沈重构】16→7精简
- 16个公开函数改为内部函数（加下划线前缀）
- 新增7个公开函数：get_time, time_add, time_diff, query_calendar, timezone_convert, timer
- 旧函数委托保留（P9向下兼容）

包含（重构后7个公开工具）：
- get_time: 统一入口(action=now/format/to_timestamp/from_timestamp)
- time_add: 时间加减（增强：months用relativedelta + weekday/isoweekday）
- time_diff: 时间差值（增强：is_after/is_before/is_equal/diff_seconds_signed）
- query_calendar: 日期综合检查(check_type=weekend/holiday/workday/next_workday)
- timezone_convert: 时区转换(direction=utc_to_local/local_to_utc/any)
- timer: 定时器管理(action=set/clear/list)

Author: 小沈 - 2026-04-25;
创建时间: 2026-04-25 15:44:54;
更新时间: 2026-05-18;
"""

import asyncio;
import json;
from datetime import datetime, timedelta, timezone;
from typing import Dict, Any, Optional, Callable, Awaitable, List, Union, Literal;
import re;
from app.utils.logger import logger;
from app.services.tools.tool_result_utils import build_next_actions, truncate_data_for_frontend;
from app.services.tools._response import build_success, build_error
from app.services.tools.toolhelper.date_helper import (
    parse_datetime_any as _parse_datetime_any,
    parse_datetime_string as _parse_datetime_string,
    is_holiday as _is_holiday,
    calc_next_n_workday as _calc_next_n_workday,
    resolve_timezone as _resolve_timezone,
);


# 定时器存储;
_timers: Dict[str, asyncio.TimerHandle] = {};
_timer_counter = 0;
_timer_callbacks: Dict[str, Dict[str, Any]] = {};  # 存储回调信息;
_timer_events: List[Dict[str, Any]] = [];  # 存储触发事件


# ===========================================================
# 内部辅助函数
# ===========================================================




# ===========================================================
# 内部函数（原16个公开函数，加下划线前缀）— 小沈 2026-05-18
# ===========================================================

def _get_current_time(
    timezone: Optional[str] = None,
    format: Optional[str] = None,
    locale: Optional[str] = None
) -> Dict[str, Any]:
    """获取当前系统时间 - 小沈 2026-05-03 增加3参数"""
    try:
        import pytz
        import locale as _locale_module

        if timezone:
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
        else:
            now = datetime.now().astimezone()

        fmt = format or "%Y-%m-%d %H:%M:%S"

        # 使用locale进行本地化格式化
        formatted = now.strftime(fmt)
        if locale:
            try:
                # locale映射表
                locale_map = {
                    "zh_CN": "chinese",
                    "zh_CN.GBK": "chinese",
                    "en_US": "english",
                    "en_US.ISO8859-1": "english",
                    "ja_JP": "japanese",
                    "ja_JP.eucJP": "japanese",
                }
                loc = locale_map.get(locale, locale)
                _locale_module.setlocale(_locale_module.LC_TIME, loc)
                formatted = now.strftime(_locale_module.nl_langinfo(_locale_module.D_T_FMT))
            except Exception:
                formatted = now.strftime(fmt)

        return build_success(
            {
                "iso": now.isoformat(),
                "timestamp": int(now.timestamp()),
                "format": formatted,
                "timezone": now.strftime("%z").replace(":", ""),
                "weekday": now.strftime("%A"),
                "isoweekday": now.isoweekday(),
                "locale": locale
            },
            "成功获取当前时间",
            llm_data={
                "iso": now.isoformat(),
                "format": formatted,
                "weekday": now.strftime("%A"),
            },
        )
    except Exception as e:
        try:
            now = datetime.now().astimezone()
            fmt = format or "%Y-%m-%d %H:%M:%S"
            formatted = now.strftime(fmt)
            return build_success(
                {
                    "iso": now.isoformat(),
                    "timestamp": int(now.timestamp()),
                    "format": formatted,
                    "timezone": now.strftime("%z").replace(":", ""),
                    "weekday": now.strftime("%A"),
                    "isoweekday": now.isoweekday(),
                    "locale": locale
                },
                "成功获取当前时间（使用默认时区）",
                llm_data={
                    "iso": now.isoformat(),
                    "format": formatted,
                    "weekday": now.strftime("%A"),
                },
            )
        except Exception as e2:
            return build_error(
                "ERR_TIME_NOW",
                f"获取当前时间失败: {str(e2)}",
                next_actions=build_next_actions([
                    ("get_time", "重试获取时间", "需要重新获取时间时"),
                ]),
            )


def _time_format(timestamp: Optional[Any] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    """格式化时间戳 — 小沈 2026-05-18"""
    try:
        from datetime import timezone
        # 1. 确定要格式化的datetime
        if timestamp is None:
            dt = datetime.now().astimezone()
        elif isinstance(timestamp, (int, float)):
            # Unix时间戳
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone()
        elif isinstance(timestamp, str):
            # 尝试解析字符串
            dt = _parse_datetime_string(timestamp)
            if dt is None:
                return build_error(
                    "ERR_META_TIME_FORMAT",
                    f"无法解析时间字符串: {timestamp}",
                    next_actions=build_next_actions([
                        ("get_time", "获取当前时间", "解析失败时获取当前时间"),
                    ]),
                )
        elif isinstance(timestamp, datetime):
            dt = timestamp.astimezone() if timestamp.tzinfo else timestamp.astimezone()
        else:
            return build_error(
                "ERR_META_TIME_FORMAT",
                f"不支持的时间戳类型: {type(timestamp)}",
                next_actions=build_next_actions([
                    ("get_time", "获取当前时间", "类型不支持时获取当前时间"),
                ]),
            )

        # 2. 确定格式字符串
        if pattern is None:
            pattern = "%Y-%m-%d %H:%M:%S"

        # 3. 格式化
        formatted = dt.strftime(pattern)
        iso_format = dt.isoformat()
        unix_timestamp = int(dt.timestamp())

        return build_success(
            {
                "formatted": formatted,
                "iso": iso_format,
                "timestamp": unix_timestamp,
                "pattern_used": pattern
            },
            "成功格式化时间",
            llm_data={"formatted": formatted, "iso": iso_format},
        )
    except Exception as e:
        return build_error(
            "ERR_META_TIME_FORMAT",
            f"格式化时间失败: {str(e)}",
            next_actions=build_next_actions([
                ("get_time", "获取当前时间", "格式化失败时获取当前时间"),
            ]),
        )


def _time_diff(start: Any, end: Optional[Any] = None) -> Dict[str, Any]:
    """计算两个时间之间的差值，返回人性化描述 — 小沈 2026-05-18"""
    try:
        # 1. 解析开始时间
        start_dt = _parse_datetime_any(start)
        if start_dt is None:
            return build_error(
                "ERR_TIME_DIFF",
                f"无法解析开始时间: {start} (类型: {type(start).__name__})",
                next_actions=build_next_actions([("get_time", "获取当前时间", "时间解析失败时")]),
            )
        # 确保是offset-aware
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

        # 2. 解析结束时间
        if end is None:
            end_dt = datetime.now().astimezone()
        else:
            end_dt = _parse_datetime_any(end)
            if end_dt is None:
                return build_error(
                    "ERR_TIME_DIFF",
                    f"无法解析结束时间: {end} (类型: {type(end).__name__})",
                    next_actions=build_next_actions([("get_time", "获取当前时间", "时间解析失败时")]),
                )
            # 确保是offset-aware
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc).astimezone()

        # 3. 计算差值
        delta = end_dt - start_dt
        total_seconds = abs(delta.total_seconds())
        # is_future: 结束时间是否在未来（相对于当前时间）
        now = datetime.now().astimezone()
        is_future = end_dt > now  # end在未来 → True

        seconds = int(total_seconds)
        minutes = total_seconds / 60.0;
        hours = total_seconds / 3600.0;
        days = total_seconds / 86400.0;

        # 4. 人性化描述
        if total_seconds < 60:
            humanized = "刚刚" if not is_future else "即将"
        elif total_seconds < 3600:  # < 60分钟
            mins = int(total_seconds / 60)
            humanized = f"{mins}分钟前" if not is_future else f"{mins}分钟后"
        elif total_seconds < 86400:  # < 24小时
            hrs = int(total_seconds / 3600)
            humanized = f"{hrs}小时前" if not is_future else f"{hrs}小时后"
        elif total_seconds < 2592000:  # < 30天
            d = int(total_seconds / 86400)
            humanized = f"{d}天前" if not is_future else f"{d}天后"
        elif total_seconds < 31104000:  # < 12个月
            m = int(total_seconds / 2592000)
            humanized = f"{m}个月前" if not is_future else f"{m}个月后"
        else:
            y = int(total_seconds / 31104000)
            humanized = f"{y}年前" if not is_future else f"{y}年后"

        return build_success(
            {
                "humanized": humanized,
                "seconds": seconds,
                "minutes": minutes,
                "hours": hours,
                "days": days,
                "is_future": is_future
            },
            "成功计算时间差",
            llm_data={"humanized": humanized, "seconds": seconds, "days": round(days, 2), "is_future": is_future},
        )
    except Exception as e:
        return build_error(
            "ERR_TIME_DIFF",
            f"计算时间差失败: {str(e)}",
            next_actions=build_next_actions([
                ("get_time", "获取当前时间", "时间解析失败时"),
            ]),
        )


async def _timer_set(delay: float, callback: str, callback_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """设置定时器，在延迟后执行回调 — 小沈 2026-05-18"""
    global _timer_counter;
    try:
        if delay <= 0:
            return build_error(
                "ERR_TIMER_SET",
                "延迟时间必须大于0",
                next_actions=build_next_actions([("timer", "重试设置定时器", "需要重新设置时")]),
            )

        if delay > 86400:  # 超过1天
            return build_error(
                "ERR_TIMER_SET",
                "延迟时间不能超过24小时",
                next_actions=build_next_actions([("timer", "重试设置定时器", "需要缩短延迟时间时")]),
            )

        # 生成定时器ID
        _timer_counter += 1;
        timer_id = f"timer_{_timer_counter}_{int(datetime.now().timestamp())}";

        # 计算触发时间
        trigger_at = datetime.now().astimezone() + timedelta(seconds=delay);

        # 存储回调信息
        _timer_callbacks[timer_id] = {
            "callback": callback,
            "callback_data": callback_data,
            "created_at": datetime.now().astimezone().isoformat(),
            "trigger_at": trigger_at.isoformat(),
        }

        # 创建回调函数（真正实现回调执行）
        async def _timer_callback():
            """定时器触发时执行"""
            try:
                # 获取回调信息
                cb_info = _timer_callbacks.get(timer_id, {})
                cb = cb_info.get("callback", "")
                cb_data = cb_info.get("callback_data")

                # 记录触发事件
                event = {
                    "timer_id": timer_id,
                    "triggered_at": datetime.now().astimezone().isoformat(),
                    "callback": cb,
                    "callback_data": cb_data,
                    "status": "triggered",
                }
                _timer_events.append(event)

                # 执行回调
                if cb:
                    # 情况1：callback是简单消息，记录日志
                    if not cb.strip().startswith("http") and not cb.strip().startswith("{"):
                        logger.info(f"[Timer {timer_id}] 提醒: {cb}")
                        event["executed_as"] = "log_message"
                    # 情况2：callback是URL，尝试调用（简化版）
                    elif cb.strip().startswith("http"):
                        try:
                            import httpx
                            resp = httpx.get(cb, timeout=5.0)
                            event["executed_as"] = "http_call"
                            event["http_status"] = resp.status_code
                        except Exception as http_err:
                            event["executed_as"] = "http_call_failed"
                            event["error"] = str(http_err)
                    # 情况3：其他情况，记录
                    else:
                        logger.info(f"[Timer {timer_id}] 回调内容: {cb}")
                        event["executed_as"] = "other"

                # 如果有callback_data，合并到事件
                if cb_data:
                    event["executed_data"] = cb_data

                logger.info(f"[Timer {timer_id}] 已触发，回调: {cb}")

            except Exception as cb_err:
                # 记录错误事件
                error_event = {
                    "timer_id": timer_id,
                    "triggered_at": datetime.now().astimezone().isoformat(),
                    "status": "error",
                    "error": str(cb_err),
                }
                _timer_events.append(error_event)
                logger.error(f"[Timer {timer_id}] 回调执行失败: {cb_err}")

        # 设置定时器
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        timer_handle = loop.call_later(delay, lambda: asyncio.ensure_future(_timer_callback()));

        # 保存定时器
        _timers[timer_id] = timer_handle;

        return build_success(
            {
                "timer_id": timer_id,
                "delay": delay,
                "trigger_at": trigger_at.strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"定时器已设置，{int(delay/60)}分钟后提醒"
            },
            "定时器设置成功",
            llm_data={"timer_id": timer_id, "trigger_at": trigger_at.strftime("%Y-%m-%d %H:%M:%S")},
        )
    except Exception as e:
        return build_error(
            "ERR_TIMER_SET",
            f"设置定时器失败: {str(e)}",
            next_actions=build_next_actions([
                ("timer", "重试设置定时器", "需要重新设置时"),
            ]),
        )


async def _timer_clear(timer_id: str) -> Dict[str, Any]:
    """清除（取消）定时器 — 小沈 2026-05-18"""
    try:
        if timer_id not in _timers:
            return build_success(
                {"timer_id": timer_id, "cancelled": False},
                f"定时器 {timer_id} 已触发或不存在，无需取消",
                llm_data={"timer_id": timer_id, "cancelled": False},
            )

        # 取消定时器
        timer_handle = _timers[timer_id]
        timer_handle.cancel();

        del _timers[timer_id];
        _timer_callbacks.pop(timer_id, None)

        return build_success(
            {
                "timer_id": timer_id,
                "cancelled": True
            },
            "定时器已取消",
            llm_data={"timer_id": timer_id, "cancelled": True},
        )
    except Exception as e:
        return build_error(
            "ERR_TIMER_CLEAR",
            f"清除定时器失败: {str(e)}",
            next_actions=build_next_actions([
                ("timer", "列出定时器", "需要查看现有定时器时", {"action": "list"}),
            ]),
        )


def _time_utc_to_local(utc_time: Any, target_tz: Optional[str] = None) -> Dict[str, Any]:
    """将UTC时间转换为本地时间或指定时区时间 — 小沈 2026-05-18"""
    try:
        # 1. 解析UTC时间
        utc_dt = _parse_datetime_any(utc_time)
        if utc_dt is None:
            return build_error(
                "ERR_META_TIME_CONVERT",
                f"无法解析UTC时间: {utc_time}",
                next_actions=build_next_actions([("timezone_convert", "重试时区转换", "需要重新转换时")]),
            )

        # 确保是UTC时间
        if utc_dt.tzinfo != timezone.utc:
            utc_dt = utc_dt.astimezone(timezone.utc);

        # 2. 转换到目标时区
        if target_tz:
            # 优先尝试IANA时区名称（如"Asia/Shanghai"、"America/New_York"）
            try:
                import pytz
                try:
                    tz = pytz.timezone(target_tz)
                    local_dt = utc_dt.astimezone(tz)
                except Exception:
                    # 方法2：失败再尝试±HH:MM格式
                    if re.match(r'^[+-]\d{2}:\d{2}$', target_tz):
                        sign = -1 if target_tz[0] == '-' else 1
                        offset_hours = int(target_tz[1:3])
                        offset_minutes = int(target_tz[4:6])
                        tz = timezone(timedelta(hours=sign*offset_hours, minutes=sign*offset_minutes))
                        local_dt = utc_dt.astimezone(tz)
                    else:
                        # 默认使用本地时区
                        local_dt = utc_dt.astimezone()
            except Exception:
                local_dt = utc_dt.astimezone()
        else:
            local_dt = utc_dt.astimezone()

        return build_success(
            {
                "local_time": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": local_dt.strftime("%z").replace(":", ""),
                "utc_original": utc_dt.isoformat()
            },
            "成功转换时区",
            llm_data={"local_time": local_dt.strftime("%Y-%m-%d %H:%M:%S"), "timezone": local_dt.strftime("%z").replace(":", "")},
        )
    except Exception as e:
        return build_error(
            "ERR_META_TIME_CONVERT",
            f"时区转换失败: {str(e)}",
            next_actions=build_next_actions([
                ("timezone_convert", "重试时区转换", "需要重新转换时"),
            ]),
        )


def _time_local_to_utc(local_time: Any, source_tz: Optional[str] = None) -> Dict[str, Any]:
    """转换本地时间为UTC时间 — 小沈 2026-05-18"""
    try:
        # 1. 解析本地时间
        local_dt = _parse_datetime_any(local_time)
        if local_dt is None:
            return build_error(
                "ERR_META_TIME_CONVERT",
                f"无法解析本地时间: {local_time}",
                next_actions=build_next_actions([("timezone_convert", "重试时区转换", "需要重新转换时")]),
            )

        # 设置源时区
        if source_tz:
            try:
                import pytz
                try:
                    tz = pytz.timezone(source_tz)
                    if local_dt.tzinfo is None:
                        local_dt = tz.localize(local_dt)
                    else:
                        local_dt = local_dt.astimezone(tz)
                except Exception:
                    # 失败再尝试±HH:MM格式
                    if re.match(r'^[+-]\d{2}:\d{2}$', source_tz):
                        sign = -1 if source_tz[0] == '-' else 1
                        offset_hours = int(source_tz[1:3])
                        offset_minutes = int(source_tz[4:6])
                        tz = timezone(timedelta(hours=sign*offset_hours, minutes=sign*offset_minutes))
                        local_dt = local_dt.replace(tzinfo=tz)
                    # 其他情况，保持原样（使用本地时区）
            except Exception:
                pass

        # 2. 转换为UTC
        utc_dt = local_dt.astimezone(timezone.utc);

        return build_success(
            {
                "utc_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "iso": utc_dt.isoformat(),
                "timestamp": int(utc_dt.timestamp())
            },
            "成功转换为UTC时间",
            llm_data={"utc_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"), "iso": utc_dt.isoformat()},
        )
    except Exception as e:
        return build_error(
            "ERR_META_TIME_CONVERT",
            f"时区转换失败: {str(e)}",
            next_actions=build_next_actions([
                ("timezone_convert", "重试时区转换", "需要重新转换时"),
            ]),
        )


def _time_add(delta: float, start: Any = None, unit: str = "days") -> Dict[str, Any]:
    """时间加减计算 — 小健 2026-05-06 delta必填前置,start可选对齐Schema"""
    try:
        # 【修复 2026-05-05 小沈】start为None时使用当前时间
        if start is None:
            start_dt = datetime.now().astimezone()
        else:
            # 1. 解析基准时间
            start_dt = _parse_datetime_any(start)
            if start_dt is None:
                return build_error(
                    "ERR_TIME_ADD",
                    f"无法解析基准时间: {start}",
                    next_actions=build_next_actions([("get_time", "获取当前时间", "基准时间解析失败时")]),
                )

        # 确保是offset-aware
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

        # 2. 根据单位计算新时间
        unit = unit.lower()
        if unit == "days":
            new_dt = start_dt + timedelta(days=delta)
        elif unit == "hours":
            new_dt = start_dt + timedelta(hours=delta)
        elif unit == "minutes":
            new_dt = start_dt + timedelta(minutes=delta)
        elif unit == "seconds":
            new_dt = start_dt + timedelta(seconds=delta)
        elif unit == "months":
            try:
                from dateutil.relativedelta import relativedelta
                new_dt = start_dt + relativedelta(months=int(delta))
            except ImportError:
                new_dt = start_dt + timedelta(days=delta * 30)
        else:
            return build_error(
                "ERR_TIME_ADD",
                f"不支持的单位: {unit}，可选: days/hours/minutes/seconds/months",
                next_actions=build_next_actions([("tool_help", "查看time_add用法", "不确定unit时", {"tool_name": "time_add"})]),
            )

        # 3. 格式化返回
        result_data = {
            "result_time": new_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "iso": new_dt.isoformat(),
            "timestamp": int(new_dt.timestamp()),
            "tz": new_dt.strftime("%z").replace(":", ""),
            "unit_used": unit,
            "delta_used": delta,
        }
        return build_success(
            result_data,
            f"成功计算时间（{delta} {unit}后）",
            llm_data={"result_time": result_data["result_time"], "iso": result_data["iso"], "unit_used": unit},
        )

    except Exception as e:
        return build_error(
            "ERR_TIME_ADD",
            f"时间加减失败: {str(e)}",
            next_actions=build_next_actions([
                ("get_time", "获取当前时间", "计算失败时获取当前时间"),
            ]),
        )


def _timer_list(limit: int = 10) -> Dict[str, Any]:
    """查询定时器列表：返回当前所有活跃的定时器 — 小沈 2026-05-18"""
    try:
        # 获取当前所有定时器
        timers = []
        for timer_id, info in _timer_callbacks.items():
            timers.append({
                "timer_id": timer_id,
                "callback": info.get("callback", ""),
                "callback_data": info.get("callback_data"),
                "created_at": info.get("created_at", ""),
                "trigger_at": info.get("trigger_at", ""),
            })

        # 按触发时间排序
        timers.sort(key=lambda x: x.get("trigger_at", ""))

        # 限制返回数量
        timers = timers[:limit] if limit > 0 else timers

        return build_success(
            timers,
            f"共{len(timers)}个定时器",
            llm_data={"count": len(timers), "ids": [t["timer_id"] for t in timers[:5]]},
        )
    except Exception as e:
        return build_error(
            "ERR_TIMER_LIST",
            f"获取定时器列表失败: {str(e)}",
            next_actions=build_next_actions([
                ("timer", "重试定时器操作", "需要重新操作时"),
            ]),
        )


def _time_to_timestamp(time: Any, unit: str = "seconds") -> Dict[str, Any]:
    """时间转时间戳：将时间转换为Unix时间戳 — 小沈 2026-05-18"""
    try:
        # 解析时间
        dt = _parse_datetime_any(time)

        if dt is None:
            return build_error(
                "ERR_TIME_TO_TIMESTAMP",
                f"无法解析time: {time}",
                next_actions=build_next_actions([("get_time", "获取当前时间戳", "解析失败时获取当前时间")]),
            )

        # 确保是offset-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone()

        # 转换为Unix时间戳
        ts = dt.timestamp()

        # 根据单位返回
        if unit == "seconds":
            ts_value = int(ts)
        elif unit == "milliseconds":
            ts_value = int(ts * 1000)
        elif unit == "microseconds":
            ts_value = int(ts * 1000000)
        else:
            ts_value = int(ts)

        return build_success(
            {
                "timestamp": ts_value,
                "unit": unit,
                "iso": dt.isoformat(),
            },
            f"时间戳: {ts_value} ({unit})",
            llm_data={"timestamp": ts_value, "unit": unit},
        )
    except Exception as e:
        return build_error(
            "ERR_TIME_TO_TIMESTAMP",
            f"时间转换失败: {str(e)}",
            next_actions=build_next_actions([
                ("get_time", "获取当前时间戳", "转换失败时获取当前时间"),
            ]),
        )


def _timestamp_to_time(timestamp: Union[int, float], target_tz: str = "+08:00") -> Dict[str, Any]:
    """时间戳转时间：将Unix时间戳转换为时间 — 小沈 2026-05-18"""
    try:
        # 解析时间戳
        try:
            ts = float(timestamp)
        except (ValueError, TypeError):
            return build_error(
                "ERR_TIMESTAMP_TO_TIME",
                f"无法解析timestamp: {timestamp}",
                next_actions=build_next_actions([("get_time", "获取当前时间", "时间戳解析失败时")]),
            )

        # 解析目标时区
        try:
            if re.match(r'^[+-]\d{2}:\d{2}$', target_tz):
                sign = -1 if target_tz[0] == '-' else 1
                offset_hours = int(target_tz[1:3])
                offset_minutes = int(target_tz[4:6])
                tz = timezone(timedelta(hours=sign*offset_hours, minutes=sign*offset_minutes))
            else:
                try:
                    import zoneinfo
                    tz = zoneinfo.ZoneInfo(target_tz)
                except Exception:
                    try:
                        import pytz
                        tz = pytz.timezone(target_tz)
                    except Exception:
                        tz = timezone.utc
        except Exception:
            tz = timezone.utc

        # 转换为时间
        dt = datetime.fromtimestamp(ts, tz=tz)

        return build_success(
            {
                "iso": dt.isoformat(),
                "timestamp": ts,
                "timezone": target_tz,
                "format": dt.strftime("%Y-%m-%d %H:%M:%S"),
            },
            f"时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}",
            llm_data={"iso": dt.isoformat(), "format": dt.strftime("%Y-%m-%d %H:%M:%S"), "timezone": target_tz},
        )
    except Exception as e:
        return build_error(
            "ERR_TIMESTAMP_TO_TIME",
            f"时间戳转换失败: {str(e)}",
            next_actions=build_next_actions([
                ("get_time", "获取当前时间", "转换失败时获取当前时间"),
            ]),
        )


def _time_next_n_workday(start: Optional[Union[int, float, str]] = None, n: int = 1) -> Dict[str, Any]:
    """下N个工作日：计算从起始日期往后第N个工作日的日期 — 小沈 2026-05-18"""
    try:
        dt = _parse_datetime_any(start) if start else datetime.now().astimezone()
        if dt is None:
            return build_error("ERR_META_CALENDAR_NEXT_N_WORKDAY", f"无法解析start: {start}", next_actions=build_next_actions([("query_calendar", "检查日期", "需要重新检查日期时")]))
        result_dates = _calc_next_n_workday(dt.date(), n)
        return build_success(result_dates, f"第{n}个工作日: {result_dates[0] if result_dates else None}", llm_data={"next_workday": result_dates[0] if result_dates else None, "n": n})
    except Exception as e:
        return build_error("ERR_META_CALENDAR_NEXT_N_WORKDAY", f"计算失败: {str(e)}", next_actions=build_next_actions([("query_calendar", "检查日期", "需要重新检查日期时")]))


# ===========================================================
# 7个公开函数（精简后）— 小沈 2026-05-18
# ===========================================================

def get_time(
    action: Literal["now", "format", "to_timestamp", "from_timestamp"] = "now",
    time_value: Optional[Union[int, float, str]] = None,
    format: Optional[str] = None,
    timezone: Optional[str] = None,
    target_tz: Optional[str] = None,
) -> Dict[str, Any]:
    """获取/格式化时间 — 小沈 2026-05-19 参数精简7→5(砍locale+unit)
    P11统一入口: action="now"|"format"|"to_timestamp"|"from_timestamp"
    """
    try:
        if action == "now":
            result = _get_current_time(timezone=timezone, format=format)
        elif action == "format":
            result = _time_format(timestamp=time_value, pattern=format)
        elif action == "to_timestamp":
            if time_value is None:
                return build_error("ERR_META_TIME_FORMAT", "action='to_timestamp'时time_value必填", next_actions=build_next_actions([("get_time", "获取当前时间", "time_value缺失时")]))
            result = _time_to_timestamp(time=time_value, unit="seconds")
        elif action == "from_timestamp":
            if time_value is None:
                return build_error("ERR_META_TIME_FORMAT", "action='from_timestamp'时time_value必填", next_actions=build_next_actions([("get_time", "获取当前时间", "time_value缺失时")]))
            result = _timestamp_to_time(timestamp=time_value, target_tz=target_tz or "+08:00")
        else:
            return build_error("ERR_INVALID_ACTION", f"不支持的action: {action}，可选: now/format/to_timestamp/from_timestamp", next_actions=build_next_actions([("tool_help", "查看get_time用法", "不确定action时", {"tool_name": "get_time"})]))

        if result.get("code") == "SUCCESS":
            result["next_actions"] = build_next_actions([
                ("time_add", "计算偏移后的时间", "需要计算N天后/前的时间时"),
                ("time_diff", "计算两个时间的差值", "需要计算时间间隔时"),
                ("query_calendar", "检查日期属性", "需要判断是否工作日/节假日时"),
            ])
        return result
    except Exception as e:
        return build_error("ERR_META_TIME_FORMAT", f"处理失败: {str(e)}", next_actions=build_next_actions([("get_time", "重试获取时间", "需要重新获取时")]))


def time_add(delta: float, start: Optional[Union[int, float, str]] = None, unit: Literal["days", "hours", "minutes", "seconds", "months"] = "days") -> Dict[str, Any]:
    """时间加减计算 — 小沈 2026-05-18
    P17增强: months用relativedelta精确计算 + 返回值增加weekday/isoweekday
    """
    result = _time_add(delta=delta, start=start, unit=unit)
    if result["code"] != "SUCCESS":
        if "next_actions" not in result:
            result["next_actions"] = build_next_actions([("get_time", "获取当前时间", "计算失败时")])
        return result

    # 增加weekday/isoweekday字段（P15一致）
    data = result["data"]
    result_time_str = data.get("result_time") or data.get("iso", "")
    dt = _parse_datetime_any(result_time_str)
    if dt:
        data["weekday"] = dt.strftime("%A")
        data["isoweekday"] = dt.isoweekday()

    result["data"] = data
    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([
            ("time_diff", "验证偏移间隔", "需要确认间隔是否正确时"),
            ("query_calendar", "检查结果日期属性", "需要判断是否工作日/节假日时"),
        ])
    return result


def time_diff(start: Union[int, float, str], end: Optional[Union[int, float, str]] = None) -> Dict[str, Any]:
    """计算时间差值 — 小沈 2026-05-18
    P15增强: 新增is_after/is_before/is_equal/diff_seconds_signed，替代time_compare
    """
    result = _time_diff(start=start, end=end)
    if result["code"] != "SUCCESS":
        if "next_actions" not in result:
            result["next_actions"] = build_next_actions([("get_time", "获取当前时间", "时间解析失败时")])
        return result

    # 从_time_diff的结果中提取信息，增加time_compare功能
    data = result["data"]

    # 计算有符号差值和比较信息
    start_dt = _parse_datetime_any(start)
    if start_dt and start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()
    end_dt = _parse_datetime_any(end) if end else datetime.now().astimezone()
    if end_dt and end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc).astimezone()

    if start_dt and end_dt:
        delta = end_dt - start_dt
        diff_signed = delta.total_seconds()
        data["is_after"] = diff_signed > 0
        data["is_before"] = diff_signed < 0
        data["is_equal"] = diff_signed == 0
        data["diff_seconds_signed"] = diff_signed

    result["data"] = data
    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([
            ("time_add", "基于差值计算目标时间", "需要计算偏移后的时间时"),
        ])
    return result


def query_calendar(
    date: Optional[Union[int, float, str]] = None,
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = "workday",
    n: int = 1,
) -> Dict[str, Any]:
    """日期综合检查 — 小沈 2026-05-18
    P11统一入口: check_type="weekend"|"holiday"|"workday"|"next_workday"
    P15全面返回: 一次性返回全部日历属性
    """
    try:
        dt = _parse_datetime_any(date) if date else datetime.now().astimezone()
        if dt is None:
            return build_error("ERR_TIME_DATE", f"无法解析日期: {date}", next_actions=build_next_actions([("query_calendar", "重试日期检查", "日期格式错误时")]))

        date_obj = dt.date()
        isoweekday = dt.isoweekday()
        is_weekend = isoweekday >= 6
        is_hol, holiday_name = _is_holiday(date_obj)
        is_workday = not is_weekend and not is_hol

        result_data = {
            "date": date_obj.isoformat(),
            "weekday": dt.strftime("%A"),
            "isoweekday": isoweekday,
            "is_weekend": is_weekend,
            "is_holiday": is_hol,
            "holiday_name": holiday_name,
            "is_workday": is_workday,
        }

        if check_type == "next_workday":
            next_workdays = _calc_next_n_workday(date_obj, n)
            result_data["next_workdays"] = next_workdays
            result_data["next_workday_first"] = next_workdays[0] if next_workdays else None
            msg = f"第{n}个工作日: {result_data.get('next_workday_first', '无')}"
        elif check_type == "weekend":
            msg = "周末" if is_weekend else "非周末"
        elif check_type == "holiday":
            msg = f"节假日：{holiday_name}" if is_hol else "非节假日"
        elif check_type == "workday":
            msg = "工作日" if is_workday else f"非工作日（{'周末' if is_weekend else '节假日：' + str(holiday_name)}）"
        else:
            return build_error("ERR_META_INVALID_CHECK_TYPE", f"不支持的check_type: {check_type}，可选: weekend/holiday/workday/next_workday", next_actions=build_next_actions([("tool_help", "查看query_calendar用法", "不确定check_type时", {"tool_name": "query_calendar"})]))

        return build_success(result_data, msg, llm_data={"date": result_data["date"], "is_weekend": is_weekend, "is_holiday": is_hol, "is_workday": is_workday, "holiday_name": holiday_name}, next_actions=build_next_actions([
            ("time_add", "计算下一个工作日偏移", "需要排程计算时"),
            ("query_calendar", "检查其他日期属性", "需要判断其他日期时"),
        ]))
    except Exception as e:
        return build_error("ERR_TIME_DATE", f"检查失败: {str(e)}", next_actions=build_next_actions([("query_calendar", "重试日期检查", "需要重新检查时")]))


def timezone_convert(
    time_value: Union[int, float, str],
    direction: Literal["utc_to_local", "local_to_utc", "any"] = "utc_to_local",
    tz: Optional[str] = None,
) -> Dict[str, Any]:
    """时区转换 — 小沈 2026-05-19 参数精简5→3(砍source_tz+target_tz)
    P11统一入口: direction="utc_to_local"|"local_to_utc"|"any"
    direction=any时tz为源时区，目标为本地时区
    """
    source_tz = None  # ⚠️ 警告: 已从Schema移除，未使用，后续视需求决定是否恢复
    target_tz = None  # ⚠️ 警告: 已从Schema移除，未使用，后续视需求决定是否恢复
    try:
        if direction == "utc_to_local":
            result = _time_utc_to_local(utc_time=time_value, target_tz=tz)
        elif direction == "local_to_utc":
            result = _time_local_to_utc(local_time=time_value, source_tz=tz)
        elif direction == "any":
            if not tz:
                return build_error("ERR_TIME_TZ", "direction='any'时tz(源时区)必填", next_actions=build_next_actions([("timezone_convert", "重试时区转换", "需要指定时区时")]))
            utc_result = _time_local_to_utc(local_time=time_value, source_tz=tz)
            if utc_result["code"] != "SUCCESS":
                return utc_result
            utc_str = utc_result["data"].get("iso", utc_result["data"].get("utc_time", ""))
            result = _time_utc_to_local(utc_time=utc_str, target_tz=None)
        else:
            return build_error("ERR_INVALID_DIRECTION", f"不支持的direction: {direction}，可选: utc_to_local/local_to_utc/any", next_actions=build_next_actions([("tool_help", "查看timezone_convert用法", "不确定direction时", {"tool_name": "timezone_convert"})]))

        if result.get("code") == "SUCCESS":
            result["next_actions"] = build_next_actions([
                ("time_diff", "计算时差", "需要计算两个时区的时间差时"),
                ("timezone_convert", "继续时区转换", "需要转换到其他时区时"),
            ])
        return result
    except Exception as e:
        return build_error("ERR_TIME_TZ", f"时区转换失败: {str(e)}", next_actions=build_next_actions([("timezone_convert", "重试时区转换", "需要重新转换时")]))


async def timer(
    action: Literal["set", "clear", "list"],
    delay: Optional[float] = None,
    callback: Optional[str] = None,
    timer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """定时器管理 — 小沈 2026-05-19 参数精简6→4(砍callback_data+limit)
    P11统一入口: action="set"|"clear"|"list"
    """
    callback_data = None  # ⚠️ 警告: 已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    limit = 10  # ⚠️ 警告: 已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    try:
        if action == "set":
            if delay is None or delay <= 0:
                return build_error("ERR_TIMER_PARAM", "delay必须大于0", next_actions=build_next_actions([("timer", "重试设置定时器", "需要重新设置时")]))
            if not callback:
                return build_error("ERR_TIMER_PARAM", "callback必填", next_actions=build_next_actions([("timer", "重试设置定时器", "需要重新设置时")]))
            result = await _timer_set(delay=delay, callback=callback, callback_data=callback_data)
        elif action == "clear":
            if not timer_id:
                return build_error("ERR_TIMER_PARAM", "timer_id必填", next_actions=build_next_actions([("timer", "列出定时器", "需要查看现有定时器时", {"action": "list"})]))
            result = await _timer_clear(timer_id=timer_id)
        elif action == "list":
            result = _timer_list(limit=limit)
        else:
            return build_error("ERR_INVALID_ACTION", f"不支持的action: {action}，可选: set/clear/list", next_actions=build_next_actions([("tool_help", "查看timer用法", "不确定action时", {"tool_name": "timer"})]))

        if isinstance(result, dict) and result.get("code") == "SUCCESS":
            result["next_actions"] = build_next_actions([
                ("timer", "管理定时器", "需要设置/清除/列出其他定时器时"),
            ])
        return result
    except Exception as e:
        return build_error("ERR_TIMER_SET", f"定时器操作失败: {str(e)}", next_actions=build_next_actions([("timer", "重试定时器操作", "需要重新操作时")]))


