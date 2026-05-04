# -*- coding: utf-8 -*-
"""
时间工具函数模块 - 为普通用户提供时间相关功能

【迁移说明】2026-04-26 小沈
- 本文件从 app/tools/time_tools.py 迁移而来

【2026-05-02 小沈重构】
- 移除所有 @register_tool 装饰器，注册由 time_register.py 显式完成
- 移除 register_tool/ToolCategory 导入
- 移除 Pydantic 模型导入（模型由 time_register.py 导入）

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- P0 核心基础（5个）：time_now, time_format, time_diff, timer_set, timer_clear;
- P1 常用辅助（4个）：time_utc_to_local, time_local_to_utc, time_is_weekend, time_is_holiday;

Author: 小沈 - 2026-04-25;
创建时间: 2026-04-25 15:44:54;
更新时间: 2026-05-02;
"""

import asyncio;
import json;
from datetime import datetime, timedelta, timezone;
from typing import Dict, Any, Optional, Callable, Awaitable;
import re;


# 定时器存储;
_timers: Dict[str, asyncio.TimerHandle] = {};
_timer_counter = 0;
_timer_callbacks: Dict[str, Dict[str, Any]] = {};  # 存储回调信息;
_timer_events: List[Dict[str, Any]] = [];  # 存储触发事件


# ===========================================================
# P0 核心基础（普通用户最高频场景）
# ===========================================================
# P0 核心基础 - time_now
# ===========================================================

def time_now(
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "iso": now.isoformat(),
                "timestamp": int(now.timestamp()),
                "format": formatted,
                "timezone": now.strftime("%z").replace(":", ""),
                "weekday": now.strftime("%A"),
                "isoweekday": now.isoweekday(),
                "locale": locale
            },
            "message": "成功获取当前时间"
        }
    except Exception as e:
        try:
            now = datetime.now().astimezone()
            fmt = format or "%Y-%m-%d %H:%M:%S"
            formatted = now.strftime(fmt)
            return {
                "code": "SUCCESS",
                "data": {
                    "iso": now.isoformat(),
                    "timestamp": int(now.timestamp()),
                    "format": formatted,
                    "timezone": now.strftime("%z").replace(":", ""),
                    "weekday": now.strftime("%A"),
                    "isoweekday": now.isoweekday(),
                    "locale": locale
                },
                "message": "成功获取当前时间（使用默认时区）"
            }
        except Exception as e2:
            return {
                "code": "ERR_TIME_NOW",
                "data": None,
                "message": f"获取当前时间失败: {str(e2)}"
            }


# ===========================================================
# P0 核心基础 - time_format
# ===========================================================

def time_format(timestamp: Optional[Any] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    """格式化时间戳"""
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
        elif isinstance(timestamp, datetime):
            dt = timestamp.astimezone() if timestamp.tzinfo else timestamp.astimezone()
        else:
            return {
                "code": "ERR_TIME_FORMAT",
                "data": None,
                "message": f"不支持的时间戳类型: {type(timestamp)}"
            }
        
        # 2. 确定格式字符串
        if pattern is None:
            pattern = "%Y-%m-%d %H:%M:%S"
        
        # 3. 格式化
        formatted = dt.strftime(pattern)
        iso_format = dt.isoformat()
        unix_timestamp = int(dt.timestamp())
        
        return {
            "code": "SUCCESS",
            "data": {
                "formatted": formatted,
                "iso": iso_format,
                "timestamp": unix_timestamp,
                "pattern_used": pattern
            },
            "message": "成功格式化时间"
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_FORMAT",
            "data": None,
            "message": f"格式化时间失败: {str(e)}"
        }


# ===========================================================
# P0 核心基础 - time_diff
# ===========================================================

def time_diff(start: Any, end: Optional[Any] = None) -> Dict[str, Any]:
    """计算两个时间之间的差值，返回人性化描述"""
    try:
        # 1. 解析开始时间
        start_dt = _parse_datetime_any(start)
        if start_dt is None:
            return {
                "code": "ERR_TIME_DIFF",
                "data": None,
                "message": f"无法解析开始时间: {start} (类型: {type(start).__name__})"
            }
        # 确保是offset-aware
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()
        
        # 2. 解析结束时间
        if end is None:
            end_dt = datetime.now().astimezone()
        else:
            end_dt = _parse_datetime_any(end)
            if end_dt is None:
                return {
                    "code": "ERR_TIME_DIFF",
                    "data": None,
                    "message": f"无法解析结束时间: {end} (类型: {type(end).__name__})"
                }
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "humanized": humanized,
                "seconds": seconds,
                "minutes": minutes,
                "hours": hours,
                "days": days,
                "is_future": is_future
            },
            "message": "成功计算时间差"
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_DIFF",
            "data": None,
            "message": f"计算时间差失败: {str(e)}"
        }


# ===========================================================
# P0 核心基础 - timer_set
# ===========================================================

async def timer_set(delay: float, callback: str, callback_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """设置定时器，在延迟后执行回调"""
    global _timer_counter;
    try:
        if delay <= 0:
            return {
                "code": "ERR_TIMER_SET",
                "data": None,
                "message": "延迟时间必须大于0"
            }
        
        if delay > 86400:  # 超过1天
            return {
                "code": "ERR_TIMER_SET",
                "data": None,
                "message": "延迟时间不能超过24小时"
            }
        
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
        loop = asyncio.get_event_loop();
        timer_handle = loop.call_later(delay, lambda: asyncio.ensure_future(_timer_callback()));
        
        # 保存定时器
        _timers[timer_id] = timer_handle;
        
        return {
            "code": "SUCCESS",
            "data": {
                "timer_id": timer_id,
                "delay": delay,
                "trigger_at": trigger_at.strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"定时器已设置，{int(delay/60)}分钟后提醒"
            },
            "message": "定时器设置成功"
        }
    except Exception as e:
        return {
            "code": "ERR_TIMER_SET",
            "data": None,
            "message": f"设置定时器失败: {str(e)}"
        }


# ===========================================================
# P0 核心基础 - timer_clear
# ===========================================================

async def timer_clear(timer_id: str) -> Dict[str, Any]:
    """清除（取消）定时器"""
    try:
        if timer_id not in _timers:
            return {
                "code": "ERR_TIMER_CLEAR",
                "data": None,
                "message": f"定时器不存在: {timer_id}"
            }
        
        # 取消定时器
        timer_handle = _timers[timer_id]
        timer_handle.cancel();
        
        # 从字典中移除
        del _timers[timer_id];
        
        return {
            "code": "SUCCESS",
            "data": {
                "timer_id": timer_id,
                "cancelled": True
            },
            "message": "定时器已取消"
        }
    except Exception as e:
        return {
            "code": "ERR_TIMER_CLEAR",
            "data": None,
            "message": f"清除定时器失败: {str(e)}"
        }


# ===========================================================
# P1 常用辅助（时区、日历相关）
# ===========================================================
# P1 常用辅助 - time_utc_to_local
# ===========================================================

def time_utc_to_local(utc_time: Any, target_tz: Optional[str] = None) -> Dict[str, Any]:
    """将UTC时间转换为本地时间或指定时区时间"""
    try:
        # 1. 解析UTC时间
        utc_dt = _parse_datetime_any(utc_time)
        if utc_dt is None:
            return {
                "code": "ERR_TIME_UTC_TO_LOCAL",
                "data": None,
                "message": f"无法解析UTC时间: {utc_time}"
            }
        
        # 确保是UTC时间
        if utc_dt.tzinfo != timezone.utc:
            utc_dt = utc_dt.astimezone(timezone.utc);
        
        # 2. 转换到目标时区
        if target_tz:
            # 优先尝试IANA时区名称（如"Asia/Shanghai"、"America/New_York"）
            try:
                # 方法1：尝试IANA时区名称（使用pytz）
                try:
                    tz = pytz.timezone(target_tz)
                    local_dt = utc_dt.astimezone(tz)
                except Exception:
                    # 方法2：失败再尝试±HH:MM格式
                    if re.match(r'^[+-]\d{2}:\d{2}$', target_tz):
                        offset_hours = int(target_tz[1:3])
                        offset_minutes = int(target_tz[4:6])
                        tz = timezone(timedelta(hours=offset_hours, minutes=offset_minutes))
                        local_dt = utc_dt.astimezone(tz)
                    else:
                        # 默认使用本地时区
                        local_dt = utc_dt.astimezone()
            except Exception:
                local_dt = utc_dt.astimezone()
        else:
            local_dt = utc_dt.astimezone()
        
        return {
            "code": "SUCCESS",
            "data": {
                "local_time": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": local_dt.strftime("%z").replace(":", ""),
                "utc_original": utc_dt.isoformat()  # 返回UTC的ISO格式
            },
            "message": "成功转换时区"
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_UTC_TO_LOCAL",
            "data": None,
            "message": f"时区转换失败: {str(e)}"
        }


# ===========================================================
# P1 常用辅助 - time_local_to_utc
# ===========================================================

def time_local_to_utc(local_time: Any, source_tz: Optional[str] = None) -> Dict[str, Any]:
    """转换本地时间为UTC时间"""
    try:
        # 1. 解析本地时间
        local_dt = _parse_datetime_any(local_time)
        if local_dt is None:
            return {
                "code": "ERR_TIME_LOCAL_TO_UTC",
                "data": None,
                "message": f"无法解析本地时间: {local_time}"
            }
        
        # 设置源时区
        if source_tz:
            try:
                # 优先尝试IANA时区名称（如"Asia/Shanghai"、"America/New_York"）
                try:
                    tz = pytz.timezone(source_tz)
                    local_dt = local_dt.replace(tzinfo=tz)
                except Exception:
                    # 失败再尝试±HH:MM格式
                    if re.match(r'^[+-]\d{2}:\d{2}$', source_tz):
                        offset_hours = int(source_tz[1:3])
                        offset_minutes = int(source_tz[4:6])
                        tz = timezone(timedelta(hours=offset_hours, minutes=offset_minutes))
                        local_dt = local_dt.replace(tzinfo=tz)
                    # 其他情况，保持原样（使用本地时区）
            except Exception:
                pass
        
        # 2. 转换为UTC
        utc_dt = local_dt.astimezone(timezone.utc);
        
        return {
            "code": "SUCCESS",
            "data": {
                "utc_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "iso": utc_dt.isoformat(),
                "timestamp": int(utc_dt.timestamp())
            },
            "message": "成功转换为UTC时间"
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_LOCAL_TO_UTC",
            "data": None,
            "message": f"时区转换失败: {str(e)}"
        }


# ===========================================================
# P1 常用辅助 - time_is_weekend
# ===========================================================

def time_is_weekend(date: Optional[Any] = None) -> Dict[str, Any]:
    """检查给定日期是否为周末"""
    try:
        # 解析日期
        if date is None:
            dt = datetime.now().astimezone()
        else:
            dt = _parse_datetime_any(date)
            if dt is None:
                return {
                    "code": "ERR_TIME_IS_WEEKEND",
                    "data": None,
                    "message": f"无法解析日期: {date}"
                }
        
        isoweekday = dt.isoweekday()  # 1=Monday, 7=Sunday;
        is_weekend = isoweekday >= 6  # Saturday or Sunday;
        
        # 构造消息
        if is_weekend:
            if isoweekday == 6:
                msg = "今天是周六，休息日"
            else:
                msg = "今天是周日，休息日"
        else:
            msg = f"今天是{dt.strftime('%A')}，工作日"
        
        return {
            "code": "SUCCESS",
            "data": {
                "is_weekend": is_weekend,
                "weekday": dt.strftime("%A"),
                "isoweekday": isoweekday,
                "date": dt.strftime("%Y-%m-%d")
            },
            "message": msg
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_IS_WEEKEND",
            "data": None,
            "message": f"检查周末失败: {str(e)}"
        }


# ===========================================================
# P1 常用辅助 - time_is_holiday
# ===========================================================

def time_is_holiday(date: Optional[Any] = None) -> Dict[str, Any]:
    """检查给定日期是否为假日"""
    try:
        # 解析日期
        if date is None:
            dt = datetime.now().astimezone()
        else:
            dt = _parse_datetime_any(date)
            if dt is None:
                return {
                    "code": "ERR_TIME_IS_HOLIDAY",
                    "data": None,
                    "message": f"无法解析日期: {date}"
                }
        
        # 简单假日检查（中国法定假日）
        month_day = (dt.month, dt.day)
        year = dt.year
        
        # 固定日期假日
        fixed_holidays = {
            (1, 1): "元旦",
            (5, 1): "劳动节",
            (10, 1): "国庆节",
        }
        
        # 动态计算的假日（简化版）
        # 清明节：4月4日或5日（查表法，2024-2030年）
        qingming_dates = {
            2024: (4, 4), 2025: (4, 4), 2026: (4, 5),
            2027: (4, 5), 2028: (4, 4), 2029: (4, 5), 2030: (4, 5),
        }
        qingming = qingming_dates.get(year, (4, 5))  # 默认4月5日
        
        is_holiday = month_day in fixed_holidays or month_day == qingming
        holiday_name = fixed_holidays.get(month_day)
        
        if month_day == qingming:
            holiday_name = "清明节"
        
        # 农历节日（待实现，需农历转换库）
        # 端午节（农历五月初五）、中秋节（农历八月十五）、春节（农历正月初一）
        # 暂未支持，标记为“农历假日需库支持”
        
        # 构造消息
        if is_holiday:
            msg = f"今天是{holiday_name}，节假日"
        else:
            msg = "今天不是节假日（注：农历假日未完全支持）"
        
        return {
            "code": "SUCCESS",
            "data": {
                "is_holiday": is_holiday,
                "holiday_name": holiday_name,
                "date": dt.strftime("%Y-%m-%d")
            },
            "message": msg
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_IS_HOLIDAY",
            "data": None,
            "message": f"检查假日失败: {str(e)}"
        }


# ===========================================================
# 内部辅助函数
# ===========================================================

def _parse_datetime_any(value: Any) -> Optional[datetime]:
    """尝试解析各种格式的时间值为datetime对象"""
    try:
        if isinstance(value, datetime):
            return value.astimezone() if value.tzinfo else value.astimezone()
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
        elif isinstance(value, str):
            return _parse_datetime_string(value)
        else:
            return None;
    except Exception:
        return None;


def _parse_datetime_string(date_str: str) -> Optional[datetime]:
    """解析日期字符串，支持多种格式"""
    try:
        date_str = date_str.strip();
        
        # 方法1：尝试ISO格式（带冒号时区）
        try:
            s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_str)
            if s != date_str:
                return datetime.fromisoformat(s)
        except ValueError:
            pass;
        
        # 方法2：尝试直接ISO格式
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass;
        
        # 方法3：尝试常见格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y年%m月%d日 %H:%M:%S",
            "%Y年%m月%d日",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.astimezone()
            except ValueError:
                continue;
        
        # 方法4：尝试提取数字
        numbers = re.findall(r'\d+', date_str)
        if len(numbers) >= 3:
            try:
                year = int(numbers[0])
                month = int(numbers[1])
                day = int(numbers[2])
                hour = int(numbers[3]) if len(numbers) > 3 else 0;
                minute = int(numbers[4]) if len(numbers) > 4 else 0;
                second = int(numbers[5]) if len(numbers) > 5 else 0;
                
                dt = datetime(year, month, day, hour, minute, second)
                return dt.astimezone()
            except Exception:
                pass;
        
        return None;
    except Exception:
        return None;
