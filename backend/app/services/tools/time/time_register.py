# -*- coding: utf-8 -*-
"""
Time Register - 时间工具注册点

【架构规范】2026-05-02 小沈
- time_register.py: 显式注册（tool_registry.register）
- time_tools.py: 工具函数实现（无装饰器）
- time_schema.py: Pydantic 模型

【2026-05-18 小沈重构】16→7精简
- 注册7个精简工具：get_time, time_add, time_diff, check_date, timezone_convert, timer
- 修复双重__all__问题
- 旧工具通过委托函数仍可调用（P9向下兼容）

创建时间: 2026-04-26
更新时间: 2026-05-18
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.time.time_schema import (
    GetTimeInput,
    TimeAddInput,
    TimeDiffInput,
    CheckDateInput,
    TimezoneConvertInput,
    TimerInput,
)

from app.services.tools.time.time_tools import (
    get_time,
    time_add,
    time_diff,
    check_date,
    timezone_convert,
    timer,
)

# ===========================================================
# 7个精简工具的描述 — 小沈 2026-05-18
# ===========================================================

TIME_TOOL_DESCRIPTIONS = {
    "get_time": """获取/格式化时间（统一入口），支持4种操作：now=获取当前时间，format=格式化时间，to_timestamp=转时间戳，from_timestamp=时间戳转时间。

使用场景：
- 当用户问"现在几点"、"当前时间"时使用action=now
- 当用户问"格式化这个时间"时使用action=format
- 当用户问"这个时间的时间戳是多少"时使用action=to_timestamp
- 当用户问"这个时间戳是什么时候"时使用action=from_timestamp

参数说明：
- action: 操作类型（now/format/to_timestamp/from_timestamp），默认now
- time_value: 时间值（format/to_timestamp/from_timestamp时必填）
- format: 输出格式，如 %Y-%m-%d %H:%M:%S
- timezone: 时区（now时有效），如 Asia/Shanghai
- locale: 本地化语言（now时有效），如 zh_CN
- unit: 时间戳单位（to_timestamp时有效）：seconds/milliseconds/microseconds
- target_tz: 目标时区（from_timestamp时有效）

返回数据说明：
- action=now: iso, timestamp, format, timezone, weekday, isoweekday, locale
- action=format: formatted, iso, timestamp, pattern_used
- action=to_timestamp: 时间戳数值
- action=from_timestamp: datetime, isoformat, timestamp, timezone""",

    "time_add": """时间加减计算：在基准时间上增加/减少偏移量，增强版支持weekday/isoweekday返回。

使用场景：
- 当用户问"当前时间+3天"、"下个月今天"时使用
- 当用户说"30分钟后提醒"需要计算目标时间时使用
- 当用户需要计算未来或过去时间时使用
- 当用户问"100天后是几号"时使用

参数说明：
- delta: 偏移量（正数=增加，负数=减少），必填
- start: 基准时间，默认当前时间
- unit: 偏移单位（days/hours/minutes/seconds/months），默认days

返回数据说明：
- result_time: 计算后的时间字符串
- iso: ISO格式时间
- timestamp: Unix时间戳
- tz: 时区
- unit_used: 实际使用的单位
- delta_used: 实际使用的偏移量
- weekday: 星期几（英文）
- isoweekday: ISO星期几（1=Monday, 7=Sunday）

注意：
- months单位使用relativedelta精确计算
- unit支持：days（天）、hours（小时）、minutes（分钟）、seconds（秒）、months（月）""",

    "time_diff": """计算时间差值（增强版），替代time_diff+time_compare，新增is_after/is_before/is_equal/diff_seconds_signed字段。

使用场景：
- 当用户问"距离 deadline 还有多长时间？"时使用
- 当用户问"这个文件多久前修改的？"时使用
- 当用户问"哪个时间更早"时使用
- 当用户问"是否已经过了某个时间"时使用

参数说明：
- start: 开始时间，必填
- end: 结束时间，默认当前时间

返回数据说明：
- humanized: 人性化描述（如"3小时前"、"2天后"）
- seconds: 总秒数（绝对值）
- minutes: 总分钟数
- hours: 总小时数
- days: 总天数
- is_future: 是否在未来
- is_after: end是否在start之后（True=end更晚）
- is_before: end是否在start之前（True=end更早）
- is_equal: 两个时间是否相等
- diff_seconds_signed: 有符号差值（正=end更晚，负=end更早）

人性化规则：
- < 60秒：刚刚
- < 60分钟：X分钟前/后
- < 24小时：X小时前/后
- < 30天：X天前/后
- < 12个月：X个月前/后
- 否则：X年前/后""",

    "check_date": """日期综合检查（四合一），统一入口检查周末/节假日/工作日/下N个工作日，一次性返回全部日历属性。

使用场景：
- 当用户问"明天是周末吗？"时使用check_type=weekend
- 当用户问"明天是假期吗？"时使用check_type=holiday
- 当用户问"明天是工作日吗"时使用check_type=workday
- 当用户问"下个工作日是几号"时使用check_type=next_workday

参数说明：
- date: 日期值，默认当前日期
- check_type: 检查类型（weekend/holiday/workday/next_workday），默认workday
- n: 第N个工作日（next_workday时有效），默认1

返回数据说明（P15全面返回）：
- date: 日期（ISO格式）
- weekday: 星期几（英文）
- isoweekday: ISO星期几（1=Monday, 7=Sunday）
- is_weekend: 是否为周末
- is_holiday: 是否为节假日
- holiday_name: 节假日名称
- is_workday: 是否为工作日
- next_workdays: 下N个工作日列表（next_workday时）
- next_workday_first: 第1个工作日（next_workday时）

支持节日列表：
    公历节日（14个+清明节）：元旦(1.1)、情人节(2.14)...
    农历节日（9个）：春节、元宵节、端午节、七夕节、中秋节...""",

    "timezone_convert": """时区转换（三方向），统一入口支持utc_to_local/local_to_utc/any三种方向，any方向可一次完成任意源→目标转换。

使用场景：
- 当用户需要将UTC时间转换为本地时间时使用direction=utc_to_local
- 当用户需要将本地时间转换为UTC时间时使用direction=local_to_utc
- 当用户需要将任意时区转换到另一时区时使用direction=any
- 当用户处理跨国时间问题时使用

参数说明：
- time_value: 时间值，必填
- direction: 转换方向（utc_to_local/local_to_utc/any），默认utc_to_local
- tz: 时区（utc_to_local时为目标时区，local_to_utc时为源时区）
- source_tz: 源时区（any时必填）
- target_tz: 目标时区（any时必填）

返回数据说明：
- direction=utc_to_local: local_time, timezone, utc_original
- direction=local_to_utc: utc_time, iso, timestamp
- direction=any: 两次转换的组合结果

常用时区：
- +08:00 或 Asia/Shanghai（北京时间）
- +00:00 或 UTC（世界协调时间）
- -05:00 或 America/New_York（纽约时间）
- +09:00 或 Asia/Tokyo（东京时间）""",

    "timer": """定时器管理（三合一），统一入口支持set/clear/list三种操作。

使用场景：
- 当用户说"3分钟后提醒我"时使用action=set
- 当用户说"取消那个定时器"时使用action=clear
- 当用户问"有哪些定时器"时使用action=list

参数说明：
- action: 操作类型（set/clear/list），必填
- delay: 延迟秒数（set时必填，1~86400）
- callback: 提醒内容（set时必填）
- callback_data: 回调附加数据（set时可选）
- timer_id: 定时器ID（clear时必填）
- limit: 返回数量限制（list时有效），默认10

返回数据说明：
- action=set: timer_id, delay, trigger_at, message
- action=clear: timer_id, cancelled
- action=list: 定时器列表

注意：
- 定时器在后台运行，使用asyncio
- set操作幂等（P16）""",
}


TIME_TOOL_EXAMPLES = {
    "get_time": [
        {"action": "now"},
        {"action": "now", "timezone": "Asia/Shanghai"},
        {"action": "now", "timezone": "America/New_York", "format": "%Y-%m-%d %H:%M:%S"},
        {"action": "format", "time_value": 1777103094},
        {"action": "format", "time_value": "2026-04-25", "format": "%Y年%m月%d日"},
        {"action": "to_timestamp", "time_value": "2026-05-05 14:30:00"},
        {"action": "from_timestamp", "time_value": 1777103094},
    ],
    "time_add": [
        {"delta": 3, "start": "2026-05-04", "unit": "days"},
        {"delta": 2, "start": 1777103094, "unit": "hours"},
        {"delta": -30, "start": "2026-05-04 12:00:00", "unit": "minutes"},
    ],
    "time_diff": [
        {"start": 1777103094},
        {"start": "2026-04-25", "end": None},
        {"start": "2026-01-01", "end": "2026-04-25"}
    ],
    "check_date": [
        {"check_type": "workday"},
        {"check_type": "weekend", "date": "2026-04-26"},
        {"check_type": "holiday", "date": "2026-10-01"},
        {"check_type": "next_workday", "n": 3},
    ],
    "timezone_convert": [
        {"time_value": "2026-04-25T12:00:00Z", "direction": "utc_to_local"},
        {"time_value": 1777103094, "direction": "utc_to_local", "tz": "+08:00"},
        {"time_value": "2026-04-25 20:00:00", "direction": "local_to_utc"},
        {"time_value": "2026-04-25 20:00:00", "direction": "any", "source_tz": "Asia/Shanghai", "target_tz": "America/New_York"},
    ],
    "timer": [
        {"action": "set", "delay": 180, "callback": "提醒用户喝水"},
        {"action": "set", "delay": 600, "callback": "执行备份", "callback_data": {"file": "D:/backup"}},
        {"action": "clear", "timer_id": "timer_1_1234567890"},
        {"action": "list"},
    ],
}


def _register_time_tools():
    """
    【2026-05-18 小沈】注册7个精简Time工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "get_time": get_time,
        "time_add": time_add,
        "time_diff": time_diff,
        "check_date": check_date,
        "timezone_convert": timezone_convert,
        "timer": timer,
    }

    TOOL_INPUT_MODELS = {
        "get_time": GetTimeInput,
        "time_add": TimeAddInput,
        "time_diff": TimeDiffInput,
        "check_date": CheckDateInput,
        "timezone_convert": TimezoneConvertInput,
        "timer": TimerInput,
    }

    for name, method in tool_methods.items():
        desc = TIME_TOOL_DESCRIPTIONS.get(name, f"Time tool: {name}")
        input_model = TOOL_INPUT_MODELS[name]
        examples = TIME_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.TIME,
            implementation=method,
            version="2.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[time_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__}, examples: {len(examples)}个")


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_time_tools"]
