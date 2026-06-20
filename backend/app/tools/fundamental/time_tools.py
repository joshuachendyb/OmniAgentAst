# -*- coding: utf-8 -*-
"""
时间工具函数模块 - 为普通用户提供时间相关功能
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【迁移说明】2026-04-26 小沈
- 本文件从 app/tools/time_tools.py 迁移而来

【2026-05-02 小沈重构】
- 移除所有 @register_tool 装饰器,注册由 time_register.py 显式完成
- 移除 register_tool/ToolCategory 导入
- 移除 Pydantic 模型导入(模型由 time_register.py 导入)

【2026-05-18 小沈重构】16→7精简
- 16个公开函数改为内部函数(加下划线前缀)
- 公开函数:time_now, time_add, time_diff, query_calendar, timezone_convert, timer(共7个,后续精简到5个)

【2026-06-12 小沈精简】7→5精简
- 删除timezone_convert(国内用户几乎不用,YAGNI)
- 公开工具: time_now, time_add, time_diff, query_calendar, timer
【2026-06-17 小欧拆分】time_now只保留"now"获取当前时间功能
- 删除format/to_timestamp/from_timestamp三种操作
- 删除_time_format/_time_to_timestamp/_timestamp_to_time内部函数

包含(重构后5个公开工具):
- time_now: 获取当前时间(只保留now操作)
- time_add: 时间加减(增强:months用relativedelta + weekday/isoweekday)
- time_diff: 时间差值(增强:is_after/is_before/is_equal/diff_seconds_signed)
- query_calendar: 日期综合检查(check_type=weekend/holiday/workday/next_workday)
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
from app.utils.common_patterns import UTC_OFFSET_PATTERN
from app.utils.logger import logger;
from app.utils.time_utils import get_timestamp_ms
from app.utils.tool_result_formatter import truncate_data_for_frontend;
from app.tools.tool_response import build_success, build_error
# 【3.18修复 北京老陈 2026-05-31】超时常量统一到tool_constants.py
from app.tools.tool_constants import HTTPX_TIMEOUT_DEFAULT
from app.tools.toolhelper.date_helper import (
    parse_datetime_any as _parse_datetime_any,
    parse_datetime_string as _parse_datetime_string,
    is_holiday as _is_holiday,
    calc_next_n_workday as _calc_next_n_workday,
    resolve_timezone as _resolve_timezone,
    get_holiday_date_by_name as _get_holiday_date_by_name,
);


# ===========================================================
# 内部函数(原16个公开函数,加下划线前缀)— 小沈 2026-05-18
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
                "成功获取当前时间(使用默认时区)",
                llm_data={
                    "iso": now.isoformat(),
                    "format": formatted,
                    "weekday": now.strftime("%A"),
                },
            )
        except Exception as e2:
            return build_error(
                ERR_TIME_NOW,
                f"获取当前时间失败: {str(e2)}",
                data={"timezone": timezone, "format": format},
            )





def _time_diff(start: Any, end: Optional[Any] = None) -> Dict[str, Any]:
    """计算两个时间之间的差值,返回人性化描述 — 小沈 2026-05-18"""
    try:
        # 1. 解析开始时间
        start_dt = _parse_datetime_any(start)
        if start_dt is None:
            return build_error(
                ERR_TIME_DIFF,
                f"无法解析开始时间: {start} (类型: {type(start).__name__})",
                data={"start": str(start)},
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
                    ERR_TIME_DIFF,
                    f"无法解析结束时间: {end} (类型: {type(end).__name__})",
                    data={"end": str(end)},
                )
            # 确保是offset-aware
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc).astimezone()

        # 3. 计算差值
        delta = end_dt - start_dt
        total_seconds = abs(delta.total_seconds())
        # is_future: 结束时间是否在未来(相对于当前时间)
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
            ERR_TIME_DIFF,
            f"计算时间差失败: {str(e)}",
            data={"start": str(start), "end": str(end)},
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
                    ERR_TIME_ADD,
                    f"无法解析基准时间: {start}",
                    data={"start": str(start), "delta": delta, "unit": unit},
                )

        # 确保是offset-aware
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

        unit = unit.lower()
        _DELTA_BUILDERS = {
            "days": timedelta(days=delta),
            "hours": timedelta(hours=delta),
            "minutes": timedelta(minutes=delta),
            "seconds": timedelta(seconds=delta),
        }
        if unit in _DELTA_BUILDERS:
            new_dt = start_dt + _DELTA_BUILDERS[unit]
        elif unit == "months":
            try:
                from dateutil.relativedelta import relativedelta
                new_dt = start_dt + relativedelta(months=int(delta))
            except ImportError:
                new_dt = start_dt + timedelta(days=delta * 30)
        else:
            return build_error(
                ERR_TIME_ADD,
                f"不支持的单位: {unit},可选: days/hours/minutes/seconds/months",
                data={"unit": unit, "delta": delta},
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
            f"成功计算时间({delta} {unit}后)",
            llm_data={"result_time": result_data["result_time"], "iso": result_data["iso"], "unit_used": unit},
        )

    except Exception as e:
        return build_error(
            ERR_TIME_ADD,
            f"时间加减失败: {str(e)}",
            data={"delta": delta, "unit": unit, "start": str(start)},
        )







# ===========================================================
# 7个公开函数(精简后)— 小沈 2026-05-18
# ===========================================================

def time_now() -> Dict[str, Any]:
    """获取当前系统时间 — 小欧 2026-06-17 只保留"now"操作; 小健 2026-06-20 删format/timezone参数"""
    format = None
    timezone = None
    try:
        result = _get_current_time(timezone=timezone, format=format)
        return result
    except Exception as e:
        return build_error(ERR_META_TIME_FORMAT, f"处理失败: {str(e)}", data={"format": format, "timezone": timezone})


def time_add(delta: float, start: Optional[Union[int, float, str]] = None, unit: Literal["days", "hours", "minutes", "seconds", "months"] = "days") -> Dict[str, Any]:
    """时间加减计算 — 小沈 2026-05-18
    P17增强: months用relativedelta精确计算 + 返回值增加weekday/isoweekday
    """
    result = _time_add(delta=delta, start=start, unit=unit)
    if result["code"] != "SUCCESS":
        return result

    # 增加weekday/isoweekday字段(P15一致)
    data = result["data"]
    result_time_str = data.get("result_time") or data.get("iso", "")
    dt = _parse_datetime_any(result_time_str)
    if dt:
        data["weekday"] = dt.strftime("%A")
        data["isoweekday"] = dt.isoweekday()

    result["data"] = data
    return result


def time_diff(start: Union[int, float, str], end: Optional[Union[int, float, str]] = None) -> Dict[str, Any]:
    """计算时间差值 — 小沈 2026-05-18
    P15增强: 新增is_after/is_before/is_equal/diff_seconds_signed,替代time_compare
    """
    result = _time_diff(start=start, end=end)
    if result["code"] != "SUCCESS":
        return result

    # 从_time_diff的结果中提取信息,增加time_compare功能
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
    return result


def query_calendar(
    date: Optional[Union[int, float, str]] = None,
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = "workday",
    n: int = 1,
    name: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """日期综合检查 — 小沈 2026-06-14
    P11统一入口: check_type="weekend"|"holiday"|"workday"|"next_workday"
    P15全面返回: 一次性返回全部日历属性
    P21新增: name参数支持按节日名称查询(如"端午节""春节""中秋节""国庆节")
    """
    try:
        # 按节日名称查询(优先级最高,忽略date/check_type)
        if name:
            holiday_info = _get_holiday_date_by_name(name, year)
            if holiday_info is None:
                return build_error(ERR_TIME_DATE, f"未找到节日名称: {name},支持:端午节/春节/中秋节/元旦/国庆节/劳动节/清明节等",
                    data={"name": name, "year": year})
            date_obj = datetime.strptime(holiday_info["date"], "%Y-%m-%d").date()
            isoweekday = holiday_info["isoweekday"]
            is_weekend = isoweekday >= 6
            is_hol, _ = _is_holiday(date_obj)
            is_workday = not is_weekend and not is_hol
            result_data = {
                "date": holiday_info["date"],
                "weekday": holiday_info["weekday"],
                "isoweekday": isoweekday,
                "is_weekend": is_weekend,
                "is_holiday": is_hol,
                "holiday_name": holiday_info["name"],
                "is_workday": is_workday,
                "holiday_type": holiday_info["type"],
                "matched_by_name": name,
            }
            msg = f"{holiday_info['name']}: {holiday_info['date']}({holiday_info['weekday']})"
            return build_success(result_data, msg,
                llm_data={"date": result_data["date"], "is_weekend": is_weekend, "is_holiday": is_hol,
                          "is_workday": is_workday, "holiday_name": holiday_info["name"]})

        # 按日期综合检查(原有逻辑)
        dt = _parse_datetime_any(date) if date else datetime.now().astimezone()
        if dt is None:
            return build_error(ERR_TIME_DATE, f"无法解析日期: {date}", data={"date": str(date)})

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
            msg = f"节假日:{holiday_name}" if is_hol else "非节假日"
        elif check_type == "workday":
            msg = "工作日" if is_workday else f"非工作日({'周末' if is_weekend else '节假日:' + str(holiday_name)})"
        else:
            return build_error(ERR_META_INVALID_CHECK_TYPE, f"不支持的check_type: {check_type},可选: weekend/holiday/workday/next_workday", data={"check_type": check_type})

        return build_success(result_data, msg, llm_data={"date": result_data["date"], "is_weekend": is_weekend, "is_holiday": is_hol, "is_workday": is_workday, "holiday_name": holiday_name})
    except Exception as e:
        return build_error(ERR_TIME_DATE, f"检查失败: {str(e)}", data={"date": str(date), "check_type": check_type})





from app.constants import (
    ERR_META_CALENDAR_NEXT_N_WORKDAY,
    ERR_META_INVALID_CHECK_TYPE,
    ERR_META_TIME_FORMAT,
    ERR_TIME_ADD,
    ERR_TIME_DATE,
    ERR_TIME_DIFF,
    ERR_TIME_NOW,
)
