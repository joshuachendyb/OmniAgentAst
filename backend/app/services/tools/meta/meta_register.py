# -*- coding: utf-8 -*-
"""
Meta Register - 元工具注册点

【2026-05-17 小沈】新建:精简方案13.12节
- tool_help: 查询工具详细用法
- tool_search: 按关键词搜索工具
"""

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.meta.meta_schema import (
    ToolHelpInput,
    ToolSearchInput,
    PipelineInput,
)

from app.services.tools.meta.meta_tools import (
    tool_help,
    tool_search,
    pipeline,
)

from app.services.tools.meta.time_tools import (
    get_time,
    time_add,
    time_diff,
    query_calendar,
    timer,
)
from app.services.tools.meta.time_schema import (
    GetTimeInput,
    TimeAddInput,
    TimeDiffInput,
    QueryCalendarInput,
    TimerInput,
)


META_TOOL_DESCRIPTIONS = {
    "tool_help": """查询指定工具的详细用法信息。返回工具名称、分类、描述、参数详情(类型/描述/是否必填)、使用示例和版本号。适用场景:当Agent需要了解某个工具的具体参数和用法、确认工具是否支持某个参数时使用。""",
    "tool_search": """按关键词搜索匹配的工具列表。返回匹配的工具列表(按相关度排序)、总匹配数和工具总数。适用场景:当用户描述需求但不确定用哪个工具、需要发现当前系统有哪些可用工具时使用。""",
    "pipeline": """定义工具执行管道,将多个工具按顺序编排执行。steps参数为JSON字符串数组,每步包含tool(工具名,必填)和params(参数,可选)。前一步的输出data会自动注入后一步的params中(核心特性)。支持stop_on_error控制是否遇错停止。适用场景:需要连续执行多个工具形成自动化流程(先A→再B→如果失败则C)、减少ReAct循环中的推理步数时使用。""",
    "get_time": """支持时间获取/格式化/转换操作功能。
action参数决定操作类型:
- now: 获取当前时间(可选format/timezone)
- format: 格式化时间,time_value(可选format)
- to_timestamp: 时间字符串→Unix时间戳,time_value
- from_timestamp: Unix时间戳→时间字符串,time_value(可选target_tz)

使用示例:
- 当前时间 → get_time(action="now")
- 转时间戳 → get_time(action="to_timestamp", time_value="2026-05-18 10:00:00")
- 格式化 → get_time(action="format", time_value="2026-05-18 10:00:00", format="%Y年%m月%d日")""",
    "time_add": """时间加减运算。支持按天/小时/分钟/秒/月进行偏移计算。delta为正数表示N个单位后的时间,delta为负数表示N个单位前的时间。返回计算后的时间字符串、ISO格式、Unix时间戳和星期信息。适用场景:需要计算N天/小时/分钟后的时间、计算某个时间点之前的时间时使用。""",
    "time_diff": """计算两个时间之间的差值。返回人类可读的差值描述以及秒/分钟/小时/天各单位的差值。可判断目标时间是否在未来/过去/相等。适用场景:需要计算两个日期相差几天、计算距某时间还有多久时使用。""",
    "query_calendar": """支持日期类型综合检查功能。
check_type参数决定检查类型:
- weekend: 判断是否为周末,date
- holiday: 判断是否为节假日,date
- workday: 判断是否为工作日,date
- next_workday: 计算下N个工作日,date(可选n)

使用示例:
- 检查周末 → query_calendar(date="2026-05-18", check_type="weekend")
- 检查节假日 → query_calendar(date="2026-05-01", check_type="holiday")
- 下个工作日 → query_calendar(date="2026-05-18", check_type="next_workday")""",
    "timer": """支持定时器的set/clear/list操作功能。
action参数决定操作类型:
- set: 设置定时器,delay+callback
- clear: 清除定时器,timer_id
- list: 列出所有定时器

使用示例:
- 设置 → timer(action="set", delay=180, callback="提醒用户喝水")
- 清除 → timer(action="clear", timer_id="timer_001")
- 列出 → timer(action="list")""",
}

META_TOOL_EXAMPLES = {
    "tool_help": [
        {"tool_name": "get_time"},
        {"tool_name": "read_csv"},
        {"tool_name": "search_files"},
    ],
    "tool_search": [
        {"query": "读取CSV文件"},
        {"query": "查找重复文件"},
        {"query": "时间格式化"},
    ],
    "pipeline": [
        {"steps": '[{"tool":"get_time","params":{"action":"now"}}]', "stop_on_error": True},
        {"steps": '[{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]'},
    ],
    # 【2026-05-19 小沈】Time工具示例,参数名与time_schema.py对齐
    "get_time": [
        {"action": "now"},
        {"action": "to_timestamp", "time_value": "2026-05-18 10:00:00"},
    ],
    "time_add": [
        {"start": "2026-05-18 10:00:00", "delta": 7, "unit": "days"},
    ],
    "time_diff": [
        {"start": "2026-05-01", "end": "2026-05-18"},
    ],
    "query_calendar": [
        {"date": "2026-05-18", "check_type": "weekend"},
    ],

    "timer": [
        {"action": "set", "delay": 180, "callback": "提醒用户喝水"},
        {"action": "list"},
    ],
}


def _register_meta_tools():
    """
    【2026-05-18 小沈】注册所有Meta工具(含Time迁入工具)
    """
    tool_methods = {
        "tool_help": tool_help,
        "tool_search": tool_search,
        "pipeline": pipeline,

        "get_time": get_time,
        "time_add": time_add,
        "time_diff": time_diff,
        "query_calendar": query_calendar,
        "timer": timer,
    }

    TOOL_INPUT_MODELS = {
        "tool_help": ToolHelpInput,
        "tool_search": ToolSearchInput,
        "pipeline": PipelineInput,

        "get_time": GetTimeInput,
        "time_add": TimeAddInput,
        "time_diff": TimeDiffInput,
        "query_calendar": QueryCalendarInput,
        "timer": TimerInput,
    }

    for name, method in tool_methods.items():
        desc = META_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = META_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.FUND_RUNTIME,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.debug(f"[meta_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


__all__ = ["_register_meta_tools"]
