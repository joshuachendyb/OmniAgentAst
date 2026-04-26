# -*- coding: utf-8 -*-
"""
时间工具函数模块 - 为普通用户提供时间相关功能

包含：
- P0 核心基础（5个）：time_now, time_format, time_diff, timer_set, timer_clear;
- P1 常用辅助（4个）：time_utc_to_local, time_local_to_utc, time_is_weekend, time_is_holiday;

Author: 小沈 - 2026-04-25;
创建时间: 2026-04-25 15:44:54;
更新时间: 2026-04-26;
"""

import asyncio;
import json;
from datetime import datetime, timedelta, timezone;
from typing import Dict, Any, Optional, Callable, Awaitable;
from pydantic import BaseModel, Field;
import re;

from app.services.tools.registry import register_tool;


# ===========================================================
# Pydantic 输入模型定义
# ===========================================================

class TimeNowInput(BaseModel):
    """time_now 工具的输入参数（无参数）"""
    pass


# 定时器存储;
_timers: Dict[str, asyncio.TimerHandle] = {};
_timer_counter = 0;


# ===========================================================
# P0 核心基础（普通用户最高频场景）
# ===========================================================
# P0 核心基础 - time_now
# ===========================================================

@register_tool(
    name="time_now",
    description="""获取当前系统时间。

使用场景：
- 当用户问"现在几点了"时使用此工具
- 当用户问"今天星期几"时使用此工具
- 当用户问"当前时间戳是多少"时使用此工具
- 当用户想要查看当前日期和时间时使用

返回数据说明：
- iso: ISO格式时间（如2026-04-26T10:30:00+08:00）
- timestamp: Unix时间戳（秒）
- format: 默认格式时间（如2026-04-26 10:30:00）
- timezone: 时区（如+0800）
- weekday: 英文星期几（如Saturday）
- isoweekday: ISO星期几（1=Monday, 7=Sunday）""",
    examples=[
        {},
    ]
)
def time_now() -> Dict[str, Any]:
    """获取当前系统时间"""
    try:
        now = datetime.now().astimezone();
        
        return {
            "code": "SUCCESS",
            "data": {
                "iso": now.isoformat(),
                "timestamp": int(now.timestamp()),
                "format": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": now.strftime("%z").replace(":", ""),  # 转为+0800格式
                "weekday": now.strftime("%A"),
                "isoweekday": now.isoweekday()  # 1=Monday, 7=Sunday
            },
            "message": "成功获取当前时间"
        }
    except Exception as e:
        return {
            "code": "ERR_TIME_NOW",
            "data": None,
            "message": f"获取当前时间失败: {str(e)}"
        }


# ===========================================================
# P0 核心基础 - time_format
# ===========================================================

@register_tool(
    name="time_format",
    description="""格式化时间戳或日期字符串为指定格式。

使用场景：
- 当用户问"这个文件什么时候改的？用中文显示"时使用此工具
- 当用户问"把当前时间格式化成YYYY年MM月DD日"时使用此工具
- 当用户需要将时间戳转换为可读格式时使用
- 当用户指定特定日期格式时使用

参数说明：
- timestamp: 时间戳（Unix秒）、日期字符串（如"2026-04-25"）、或datetime对象。如果为None，则使用当前时间。支持格式：int/float=Unix时间戳，str=日期字符串自动识别，datetime=直接使用。默认为None（当前时间）
- pattern: 格式字符串（如"%Y-%m-%d %H:%M:%S"）。如果为None，则使用默认格式"%Y-%m-%d %H:%M:%S"。常用格式：%Y年%m月%d日、%Y-%m-%d %H:%M:%S、%Y/%m/%d。默认为None（%Y-%m-%d %H:%M:%S）

返回数据说明：
- formatted: 格式化后的字符串
- iso: ISO格式时间
- timestamp: Unix时间戳
- pattern_used: 实际使用的格式""",
    examples=[
        {},
        {"timestamp": 1777103094},
        {"timestamp": None, "pattern": "%Y年%m月%d日"},
        {"timestamp": "2026-04-25", "pattern": "%Y/%m/%d"}
]
)
def time_format(timestamp: Optional[Any] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    """格式化时间戳"""
    try:
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

@register_tool(
    name="time_diff",
    description="""计算两个时间之间的差值，返回人性化描述。

使用场景：
- 当用户问"我上次问这个是什么时候？"时使用此工具
- 当用户问"这个文件多久前修改的？"时使用此工具
- 当用户问"距离 deadline 还有多长时间？"时使用此工具
- 当用户想要知道两个时间点之间相差多久时使用

参数说明：
- start: 开始时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数
- end: 结束时间（时间戳、字符串、datetime）。如果为None则使用当前时间。支持格式同start。可选参数，默认为None（当前时间）

返回数据说明：
- humanized: 人性化描述（如"3小时前"、"2天后"）
- seconds: 总秒数
- minutes: 总分钟数
- hours: 总小时数
- days: 总天数
- is_future: 是否在未来（True=未来，False=过去）

人性化规则：
- < 60秒：刚刚
- < 60分钟：X分钟前/后
- < 24小时：X小时前/后
- < 30天：X天前/后
- < 12个月：X个月前/后
- 否则：X年前/后""",
    examples=[
        {"start": 1777103094},
        {"start": "2026-04-25", "end": None},
        {"start": "2026-01-01", "end": "2026-04-25"}
    ]
)
def time_diff(start: Any, end: Optional[Any] = None) -> Dict[str, Any]:
    """
    计算两个时间之间的差值，返回人性化描述
    
    Args:
        start: 开始时间（时间戳、字符串、datetime）
        end: 结束时间（时间戳、字符串、datetime），如果为None则使用当前时间
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "humanized": "3小时前",  # 人性化描述
                "seconds": 10800,  # 总秒数
                "minutes": 180.0,  # 总分钟数
                "hours": 3.0,  # 总小时数
                "days": 0,  # 总天数
                "is_future": false  # 是否在未来
            },
"message": "成功计算时间差"
        }
     
    """
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

@register_tool(
    name="timer_set",
    description="""设置定时器，在指定延迟后执行回调。

使用场景：
- 当用户说"3分钟后提醒我"时使用此工具
- 当用户说"10分钟后执行这个任务"时使用此工具
- 当用户需要定时执行某个动作时使用
- 当用户设置提醒或定时任务时使用

参数说明：
- delay: 延迟时间（秒）。必须大于0，不能超过86400秒（24小时）。必填参数
- callback: 回调函数标识或描述（字符串）。描述要执行的操作。必填参数
- callback_data: 传递给回调的数据（可选）。可选参数，默认为None

返回数据说明：
- timer_id: 定时器ID（如timer_1_1234567890）
- delay: 实际设置的延迟（秒）
- trigger_at: 触发时间（ISO格式）

注意：
- 定时器在后台运行，使用asyncio
- 回调函数通过字符串描述实现""",
    examples=[
        {"delay": 180, "callback": "提醒用户喝水"},
        {"delay": 600, "callback": "执行备份", "callback_data": {"file": "D:/backup"}},
        {"delay": 3600, "callback": "发送报告邮件"}
    ]
)
async def timer_set(delay: float, callback: str, callback_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    设置定时器，在延迟后执行回调
    
    Args:
        delay: 延迟时间（秒）
        callback: 回调函数标识或描述（字符串）
        callback_data: 传递给回调的数据（可选）
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "timer_id": "timer_123456",
                "delay": 180,
                "trigger_at": "2026-04-25 15:47:54"
            },
            "message": "定时器已设置，3分钟后提醒"
        }
    
    场景：
        - 用户说：“3分钟后提醒我”
        - 用户说：“10分钟后执行这个任务”
    
    注意：
        - 定时器在后台运行，使用asyncio;
        - 回调函数需要实现为字符串描述，因为跨进程限制;
        - 实际项目中，回调可能通过消息队列或事件总线实现
    
    Author: 小沈 - 2026-04-25;
    """
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
        
        # 创建回调函数（这里用简单的打印，实际项目需要更复杂的实现）
        async def _timer_callback():
            print(f"[Timer {timer_id}] 触发: {callback}");
            # 实际项目中，这里应该发送通知或执行任务;
            # 例如：await notify_user(f"提醒: {callback}", callback_data);
        
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

@register_tool(
    name="timer_clear",
    description="""清除（取消）已设置的定时器。

使用场景：
- 当用户说"取消那个定时器"时使用此工具
- 当用户想要取消之前设置的提醒时使用
- 当用户取消定时任务时使用

参数说明：
- timer_id: 定时器ID（由timer_set返回）。必填参数

返回数据说明：
- timer_id: 被清除的定时器ID
- cancelled: 是否成功取消（True=成功）

注意：
- 如果定时器已经触发，返回cancelled=False""",
    examples=[
        {"timer_id": "timer_1_1234567890"},
        {"timer_id": "timer_2_1234567890"}
    ]
)
async def timer_clear(timer_id: str) -> Dict[str, Any]:
    """
    清除（取消）定时器
    
    Args:
        timer_id: 定时器ID（由timer_set返回）
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "timer_id": "timer_123456",
                "cancelled": true
            },
            "message": "定时器已取消"
        }
    
    场景：
        - 用户说：“别提醒我了”
        - 用户说：“取消那个定时器”
    
    Author: 小沈 - 2026-04-25;
    """
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

def time_utc_to_local(utc_time: Any, target_tz: Optional[str] = None) -> Dict[str, Any]:
    """
    将UTC时间转换为本地时间或指定时区时间
    
    Args:
        utc_time: UTC时间（时间戳、字符串、datetime）
        target_tz: 目标时区（如"+08:00"、"Asia/Shanghai"），如果为None则使用本地时区
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "local_time": "2026-04-25 23:44:54",
                "timezone": "+0800",
                "utc_original": "2026-04-25T15:44:54+00:00"
            },
            "message": "成功转换时区"
        }
    
    场景：
        - 跨时区用户问：“现在UTC时间是几点？请用北京时间显示”
    
    Author: 小沈 - 2026-04-25;
    """
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
            # 尝试解析时区字符串
            try:
                # 简单处理：如果格式是+08:00，则计算偏移
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


def time_local_to_utc(local_time: Any, source_tz: Optional[str] = None) -> Dict[str, Any]:
    """
    将本地时间转换为UTC时间
    
    Args:
        local_time: 本地时间（时间戳、字符串、datetime）
        source_tz: 源时区（如"+08:00"、"Asia/Shanghai"），如果为None则使用本地时区
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "utc_time": "2026-04-25 15:44:54",
                "iso": "2026-04-25T15:44:54+00:00",
                "timestamp": 1777103094
            },
            "message": "成功转换为UTC时间"
        }
    
    Author: 小沈 - 2026-04-25;
    """
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
            # 简单处理时区偏移
            if re.match(r'^[+-]\d{2}:\d{2}$', source_tz):
                offset_hours = int(source_tz[1:3])
                offset_minutes = int(source_tz[4:6])
                tz = timezone(timedelta(hours=offset_hours, minutes=offset_minutes))
                local_dt = local_dt.replace(tzinfo=tz)
        
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


def time_is_weekend(date: Optional[Any] = None) -> Dict[str, Any]:
    """
    检查给定日期是否为周末
    
    Args:
        date: 日期（时间戳、字符串、datetime），如果为None则使用当前日期
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "is_weekend": true,
                "weekday": "Saturday",
                "isoweekday": 6,  # 6=Saturday, 7=Sunday;
                "date": "2026-04-25"
            },
            "message": "今天是周末"
        }
    
    场景：
        - 用户问：“明天要上班吗？”
        - 用户问：“这周六是休息日吗？”
    
    Author: 小沈 - 2026-04-25;
    """
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


def time_is_holiday(date: Optional[Any] = None) -> Dict[str, Any]:
    """
    检查给定日期是否为假日（简单实现，实际需要节假日API）
    
    Args:
        date: 日期（时间戳、字符串、datetime），如果为None则使用当前日期
    
    返回：
        dict: {
            "code": "SUCCESS",
            "data": {
                "is_holiday": false,
                "holiday_name": null,  # 如果是假日，这里会有名称
                "date": "2026-04-25"
            },
            "message": "今天不是节假日"
        }
    
    注意：
        - 这是简单实现，只检查固定的几个假日（如元旦、春节等）
        - 实际项目中应该调用节假日API或使用完整日历数据
    
    场景：
        - 用户问：“今天是不是节假日？”
        - 用户问：“国庆节放几天假？”
    
    Author: 小沈 - 2026-04-25;
    """
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
        
        # 简单假日检查（固定日期）
        # 实际项目中应该使用节假日API
        month_day = (dt.month, dt.day);
        
        # 定义一些固定假日（简化版）
        fixed_holidays = {
            (1, 1): "元旦",
            (5, 1): "劳动节",
            (10, 1): "国庆节",
            # 注意：春节、清明、端午、中秋等是农历，这里不处理;
        }
        
        is_holiday = month_day in fixed_holidays;
        holiday_name = fixed_holidays.get(month_day);
        
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
    """
    尝试解析各种格式的时间值为datetime对象
    
    Args:
        value: 可以是时间戳（int/float）、字符串、datetime对象
    
    Returns:
        datetime对象，解析失败返回None;
    """
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
    """
    解析日期字符串，支持多种格式
    
    支持格式：
        - ISO格式：2026-04-25T15:44:54+08:00;
        - 简单日期：2026-04-25;
        - 简单日期时间：2026-04-25 15:44:54;
        - 斜杠格式：2026/04/25;
        - 中文格式：2026年04月25日;
        - 带T的ISO格式（不带时区）：2026-04-25T15:44:54;
        - 带T和微秒的ISO格式：2026-04-25T15:44:54.123456;
        - 带T和时区的ISO格式：2026-04-25T15:44:54+08:00;
    
    Returns:
        datetime对象，解析失败返回None;
    """
    try:
        # 去除空格
        date_str = date_str.strip();
        
        # 方法1：尝试ISO格式（带冒号时区）
        try:
            # 处理时区中的冒号：+08:00 → +0800
            s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_str)
            if s != date_str:  # 确实去除了冒号
                return datetime.fromisoformat(s)
        except ValueError:
            pass;
        
        # 方法2：尝试直接ISO格式（可能不带时区）
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass;
        
        # 方法3：尝试常见格式（带T）
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y年%m月%d日 %H:%M:%S",
            "%Y年%m月%d日",
            "%Y-%m-%dT%H:%M:%S",          # 带T不带时区
            "%Y-%m-%dT%H:%M:%S.%f",    # 带T和微秒
            "%Y-%m-%dT%H:%M:%S%z",       # 带T和时区（无冒号）
            "%Y-%m-%dT%H:%M:%S.%f%z",   # 带T、微秒和时区
        ]
        
        for fmt in formats:
            try:
                # 没有时区的，假设为本地时间
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
    except Exception:
        return None;
