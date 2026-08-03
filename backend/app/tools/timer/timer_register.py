# -*- coding: utf-8 -*-
"""
Timer Register - 定时器工具注册点 — 小欧 2026-06-17

6个工具:
- timer_set: 设置定时器
- timer_clear: 清除定时器
- timer_list: 列出定时器
- timeadd: 时间加减运算 (从FUNDAMENTAL迁入)
- timediff: 时间差值计算 (从FUNDAMENTAL迁入)
- calendar: 节日/日期查询 (从FUNDAMENTAL迁入)
【2026-07-20 小欧】加描述规范:工具描述保持简洁不冗余,能力详情与默认支持能力只写在 schema 类 docstring,禁止在 register 工具描述里重复
【2026-07-28 - 小欧 - BUG#10: timer工具依赖列表中httpx/httpcore为复制粘贴错误(timer仅使用asyncio/datetime, 不依赖HTTP客户端), 清空3工具依赖列表】
【2026-07-28 北京老陈】timeadd/timediff/calendar 从 FUNDAMENTAL 迁入
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

# 定时器工具依赖配置 — 小健 2026-06-18

TIMER_TOOL_DEPENDENCIES = {
    "timer_set": [],
    "timer_clear": [],
    "timer_list": [],
    "timeadd": [],
    "timediff": [],
    "calendar": [],
}

from app.tools.timer.timer_schema import (
    TimerSetInput,
    TimerClearInput,
    TimerListInput,
    TimeAddInput,
    TimeDiffInput,
    QueryCalendarInput,
)

from app.tools.timer.timer_set import timer_set
from app.tools.timer.timer_clear import timer_clear
from app.tools.timer.timer_list import timer_list
from app.tools.timer.time_add import timeadd
from app.tools.timer.time_diff import timediff
from app.tools.timer.query_calendar import calendar


# 【描述规范】2026-07-20 北京老陈 — 工具描述(本 TIMER_TOOL_DESCRIPTIONS 字典)保持简洁、不冗余:
# 能力详情与默认支持的能力只写在对应 Schema 类的 docstring 里(会进入 JSON Schema 发给 LLM);
# 本字典仅作一句话路由/适用场景说明,严禁重复 schema docstring 内容。
TIMER_TOOL_DESCRIPTIONS = {
    "timer_set": """设置一个定时器,在指定的延迟后触发提醒。delay为延迟秒数(1~86400,最长24小时),callback为触发时的提醒内容。适用场景:需要延迟执行提醒、定时通知用户时使用。""",

    "timer_clear": """清除(取消)一个已设置的定时器。timer_id为必填参数,由timer_set返回的完整ID。适用场景:需要取消已设置的定时器时使用。""",

    "timer_list": """列出当前所有活跃的定时器。返回定时器ID、回调内容、创建时间和触发时间,按触发时间排序。适用场景:需要查看有哪些定时器在运行、确认定时器状态时使用。""",

    "timeadd": """对时间进行加减偏移运算,支持天/小时/分钟/秒/月。适用场景:需要计算N个单位后的时间或某个时间点之前的时间时使用。""",

    "timediff": """计算两个时间之间的差值。适用场景:需要计算日期差、距离某时间还有多久时使用。""",

    "calendar": """查询节日日期和假期信息。适用场景:需要了解节日日期、判断日期类型(周末/节假日/工作日)时使用。""",
}

TIMER_TOOL_EXAMPLES = {
    "timer_set": [
        {"delay": 180, "callback": "提醒用户喝水"},
        {"delay": 600, "callback": "任务超时提醒"},
    ],
    "timer_clear": [
        {"timer_id": "timer_1_1234567890"},
    ],
    "timer_list": [
        {},
    ],
    "timeadd": [
        {"delta": 7},
        {"delta": 7, "unit": "days"},
        {"delta": 3, "unit": "hours"},
        {"delta": 30, "unit": "minutes"},
        {"delta": 90, "unit": "seconds"},
        {"delta": 2, "unit": "months"},
        {"delta": -7, "unit": "days"},
        {"start": "2026-05-18 10:00:00", "delta": 7, "unit": "days"},
    ],
    "timediff": [
        {"start": "2026-05-01"},
        {"start": "2026-05-01", "end": "2026-05-18"},
        {"start": 1717200000, "end": 1717804800},
    ],
    "calendar": [
        {"name": "端午节", "year": 2026},
        {"name": "春节", "year": 2026},
        {"name": "中秋节", "year": 2026},
        {"name": "国庆节", "year": 2026},
        {"name": "元旦", "year": 2026},
        {"name": "2026-05-18"},
        {"name": "2026-06-24"},
    ],
}

TIMER_INPUT_MODELS = {
    "timer_set": TimerSetInput,
    "timer_clear": TimerClearInput,
    "timer_list": TimerListInput,
    "timeadd": TimeAddInput,
    "timediff": TimeDiffInput,
    "calendar": QueryCalendarInput,
}


def _register_timer_tools():
    """注册6个定时器工具 — 小欧 2026-06-17"""
    tool_methods = {
        "timer_set": timer_set,
        "timer_clear": timer_clear,
        "timer_list": timer_list,
        "timeadd": timeadd,
        "timediff": timediff,
        "calendar": calendar,
    }

    for name, method in tool_methods.items():
        desc = TIMER_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TIMER_INPUT_MODELS.get(name)
        examples = TIMER_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.TIMER,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            dependencies=TIMER_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(
            f"[timer_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


__all__ = ["_register_timer_tools"]
