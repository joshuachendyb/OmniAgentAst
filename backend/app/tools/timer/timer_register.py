# -*- coding: utf-8 -*-
"""
Timer Register - 定时器工具注册点 — 小欧 2026-06-17

3个工具:
- timer_set: 设置定时器
- timer_clear: 清除定时器
- timer_list: 列出定时器
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 定时器工具依赖配置 — 小健 2026-06-18

TIMER_TOOL_DEPENDENCIES = {
    "timer_set": ["httpx==0.26.0", "httpcore==1.0.1"],
    "timer_clear": ["httpx==0.26.0", "httpcore==1.0.1"],
    "timer_list": ["httpx==0.26.0", "httpcore==1.0.1"],
}

from app.tools.timer.timer_schema import (
    TimerSetInput,
    TimerClearInput,
    TimerListInput,
)

from app.tools.timer.timer_tools import (
    timer_set,
    timer_clear,
    timer_list,
)


TIMER_TOOL_DESCRIPTIONS = {
    "timer_set": """设置一个定时器,在指定的延迟后触发提醒。delay为延迟秒数(1~86400,最长24小时),callback为触发时的提醒内容。适用场景:需要延迟执行提醒、定时通知用户时使用。""",

    "timer_clear": """清除(取消)一个已设置的定时器。timer_id为必填参数,由timer_set返回的完整ID。适用场景:需要取消已设置的定时器时使用。""",

    "timer_list": """列出当前所有活跃的定时器。返回定时器ID、回调内容、创建时间和触发时间,按触发时间排序。适用场景:需要查看有哪些定时器在运行、确认定时器状态时使用。""",
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
}

TIMER_INPUT_MODELS = {
    "timer_set": TimerSetInput,
    "timer_clear": TimerClearInput,
    "timer_list": TimerListInput,
}


def _register_timer_tools():
    """注册3个定时器工具 — 小欧 2026-06-17"""
    tool_methods = {
        "timer_set": timer_set,
        "timer_clear": timer_clear,
        "timer_list": timer_list,
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
