# -*- coding: utf-8 -*-
"""
Time Register - 时间工具注册点

【架构规范】2026-05-02 小沈
- time_register.py: 显式注册（tool_registry.register）
- time_tools.py: 工具函数实现（无装饰器）
- time_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册（tool_registry.register）
- 按 shell_register.py 模式重写

创建时间: 2026-04-26
更新时间: 2026-05-02
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.time.time_schema import (
    TimeNowInput,
    TimeFormatInput,
    TimeDiffInput,
    TimerSetInput,
    TimerClearInput,
    TimeUtcToLocalInput,
    TimeLocalToUtcInput,
    TimeIsWeekendInput,
    TimeIsHolidayInput,
    TimeAddInput,
    TimerListInput,
    TimeCompareInput,
    TimeToTimestampInput,
    TimestampToTimeInput,
    TimeIsWorkdayInput,
    TimeNextNWorkdayInput,
)

from app.services.tools.time.time_tools import (
    time_now,
    time_format,
    time_diff,
    timer_set,
    timer_clear,
    time_utc_to_local,
    time_local_to_utc,
    time_is_weekend,
    time_is_holiday,
    time_add,
    timer_list,
    time_compare,
    time_to_timestamp,
    timestamp_to_time,
    time_is_workday,
    time_next_n_workday,
)

TIME_TOOL_DESCRIPTIONS = {
    "get_current_time": """获取当前系统时间，支持时区、格式和本地化设置。

使用场景：
- 当用户需要获取当前时间时使用
- 当用户想要以特定格式显示时间时使用
- 当用户需要进行时间相关的计算时使用

参数说明：
- timezone：时区（可选），默认跟随系统时区
- format：输出格式（可选），默认 %Y-%m-%d %H:%M:%S
- locale：本地化语言（可选），默认匹配当前会话语言

【重要】返回格式化后的当前时间字符串

返回数据说明：
- iso: ISO格式时间（如2026-04-26T10:30:00+08:00）
- timestamp: Unix时间戳（秒）
- format: 默认格式时间（如2026-04-26 10:30:00）
- timezone: 时区（如+0800）
- weekday: 星期几（如Saturday）
- isoweekday: ISO星期几（1=Monday, 7=Sunday）
- locale: 本地化语言标识""",
    "time_format": """格式化时间戳或日期字符串为指定格式。

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
    "time_diff": """计算两个时间之间的差值，返回人性化描述。

使用场景：
- 当用户问"我上次问这个是什么时候？"时使用此工具
- 当用户问"这个文件多久前修改的？"时使用此工具
- 当用户问"距离 deadline 还有多长时间？"时使用此工具
- 当用户想要知道两个时间点之间相差多久时使用

参数说明：
- start: 开始时间（时间戳、字符串、datetime）。可选参数，默认为None（当前时间）
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
    "timer_set": """设置定时器，在指定延迟后执行回调。

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
    "timer_clear": """清除（取消）已设置的定时器。

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
    "time_utc_to_local": """将UTC时间转换为本地时间或指定时区时间。

使用场景：
- 当用户需要将UTC时间转换为本地时间时使用此工具
- 当用户在不同时区间转换时间时使用
- 当用户处理跨国时间问题时使用
- 当用户指定目标时区时使用

参数说明：
- utc_time: UTC时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数
- target_tz: 目标时区（如"+08:00"、"Asia/Shanghai"）。如果为None则使用本地时区。可选参数，默认为None（本地时区）

返回数据说明：
- utc_time: 原始UTC时间
- local_time: 转换后的本地时间
- target_tz: 目标时区

常用时区：
- +08:00 或 Asia/Shanghai（北京时间）
- +00:00 或 UTC（世界协调时间）
- -05:00 或 America/New_York（纽约时间）
- +09:00 或 Asia/Tokyo（东京时间）""",
    "time_local_to_utc": """将本地时间或指定时区时间转换为UTC时间。

使用场景：
- 当用户需要将本地时间转换为UTC时间时使用此工具
- 当用户在跨国协作中需要统一到UTC时间时使用
- 当用户需要提交UTC时间给系统时使用
- 当用户指定源时区时使用

参数说明：
- local_time: 本地时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数
- source_tz: 源时区（如"+08:00"、"Asia/Shanghai"）。如果为None则使用本地时区。可选参数，默认为None（本地时区）

返回数据说明：
- utc_time: 转换后的UTC时间
- source_tz: 源时区

常用时区：参考time_utc_to_local""",
    "time_is_weekend": """检查给定日期是否为周末（周六或周日）。

使用场景：
- 当用户问"明天是周末吗？"时使用此工具
- 当用户问"这个日期是周末吗？"时使用此工具
- 当用户需要判断是否可以安排周末活动时使用
- 当用户想要知道某天是否需要上班时使用

参数说明：
- date: 日期（时间戳、字符串、datetime）。如果为None则使用当前日期。可选参数，默认为None（当前日期）

返回数据说明：
- is_weekend: 是否为周末（True=是周末，False=不是周末）
- date: 输入的日期
- weekday: 星期几（英文）
- isoweekday: ISO星期几（1=Monday, 7=Sunday）

注意：
- 周六和周日被认为是周末
- 使用ISO标准：Monday=1, Tuesday=2, ..., Sunday=7""",
    "time_is_holiday": """检查给定日期是否为假日（仅支持4个固定节日）。
    
使用场景：
    - 当用户问"明天是假期吗？"时使用此工具
    - 当用户问"这个日期是法定节假日吗？"时使用此工具
    - 当用户需要安排假期活动时使用
    - 当用户想要知道某天是否放假时使用
    
参数说明：
    - date: 日期（时间戳、字符串、datetime）。如果为None则使用当前日期。可选参数，默认为None（当前日期）
    
返回数据说明：
    - is_holiday: 是否为假日（True=是假日，False=不是假日）
    - date: 输入的日期
    - holiday_name: 假日名称
    
注意：
    - 当前支持4个固定节日：元旦（1月1日）、劳动节（5月1日）、国庆节（10月1日）、清明节（4月4或5日）
    - 春节、端午、中秋等农历假日未支持
    - 农历假日建议使用专门的节假日API""",
    
    "time_add": """时间加减计算：在基准时间上增加/减少偏移量。
    
使用场景：
    - 当用户问"当前时间+3天"、"下个月今天"时使用此工具
    - 当用户说"30分钟后提醒"需要计算目标时间时使用
    - 当用户需要计算未来或过去时间时使用
    - 当用户问"100天后是几号"时使用此工具
    
参数说明：
    - start: 基准时间（时间戳、字符串、datetime）。可选参数，默认为None（当前时间）。不填则使用当前时间
    - delta: 偏移量（数字）。正数表示增加，负数表示减少。必填参数
    - unit: 单位（days/hours/minutes/seconds/months）。默认为days。Agent 语义解析：'3天'→unit='days'，'2小时'→unit='hours'。可选参数，默认为days
    
返回数据说明：
    - result_time: 计算后的时间字符串（默认格式）
    - iso: ISO格式时间
    - timestamp: Unix时间戳
    - tz: 时区
    - unit_used: 实际使用的单位
    - delta_used: 实际使用的偏移量
    
注意：
    - months单位按30天简化计算
    - unit支持：days（天）、hours（小时）、minutes（分钟）、seconds（秒）、months（月）""",
    }

TIME_TOOL_EXAMPLES = {
    "get_current_time": [
        {},
        {"timezone": "Asia/Shanghai"},
        {"timezone": "America/New_York", "format": "%Y-%m-%d %H:%M:%S"},
    ],
    "time_format": [
        {},
        {"timestamp": 1777103094},
        {"timestamp": None, "pattern": "%Y年%m月%d日"},
        {"timestamp": "2026-04-25", "pattern": "%Y/%m/%d"}
    ],
    "time_diff": [
        {"start": 1777103094},
        {"start": "2026-04-25", "end": None},
        {"start": "2026-01-01", "end": "2026-04-25"}
    ],
    "timer_set": [
        {"delay": 180, "callback": "提醒用户喝水"},
        {"delay": 600, "callback": "执行备份", "callback_data": {"file": "D:/backup"}},
        {"delay": 3600, "callback": "发送报告邮件"}
    ],
    "timer_clear": [
        {"timer_id": "timer_1_1234567890"},
        {"timer_id": "timer_2_1234567890"}
    ],
    "time_utc_to_local": [
        {"utc_time": "2026-04-25T12:00:00Z"},
        {"utc_time": 1777103094, "target_tz": "+08:00"},
        {"utc_time": "2026-04-25T12:00:00Z", "target_tz": "Asia/Shanghai"}
    ],
    "time_local_to_utc": [
        {"local_time": "2026-04-25 20:00:00"},
        {"local_time": "2026-04-25T20:00:00", "source_tz": "+08:00"},
        {"local_time": "2026-04-25 20:00:00", "source_tz": "Asia/Shanghai"}
    ],
    "time_is_weekend": [
        {},
        {"date": "2026-04-25"},
        {"date": "2026-04-26"},
        {"date": 1777103094}
    ],
    "time_is_holiday": [
        {},
        {"date": "2026-01-01"},
        {"date": "2026-10-01"},
        {"date": "2026-04-05"}
    ],
    "time_add": [
        {"start": "2026-05-04", "delta": 3, "unit": "days"},
        {"start": 1777103094, "delta": 2, "unit": "hours"},
        {"start": "2026-05-04 12:00:00", "delta": -30, "unit": "minutes"},
    ],
}


def _register_time_tools():
    """
    【2026-05-02 小沈】显式注册所有Time工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "get_current_time": time_now,
        "time_format": time_format,
        "time_diff": time_diff,
        "timer_set": timer_set,
        "timer_clear": timer_clear,
        "time_utc_to_local": time_utc_to_local,
        "time_local_to_utc": time_local_to_utc,
        "time_is_weekend": time_is_weekend,
        "time_is_holiday": time_is_holiday,
        "time_add": time_add,
    }

    TOOL_INPUT_MODELS = {
        "get_current_time": TimeNowInput,
        "time_format": TimeFormatInput,
        "time_diff": TimeDiffInput,
        "timer_set": TimerSetInput,
        "timer_clear": TimerClearInput,
        "time_utc_to_local": TimeUtcToLocalInput,
        "time_local_to_utc": TimeLocalToUtcInput,
        "time_is_weekend": TimeIsWeekendInput,
        "time_is_holiday": TimeIsHolidayInput,
        "time_add": TimeAddInput,
    }

    for name, method in tool_methods.items():
        desc = TIME_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = TIME_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.TIME,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[time_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


_register_time_tools()


__all__ = [
    "time_now",
    "time_format",
    "time_diff",
    "timer_set",
    "timer_clear",
    "time_utc_to_local",
    "time_local_to_utc",
    "time_is_weekend",
    "time_is_holiday",
]
