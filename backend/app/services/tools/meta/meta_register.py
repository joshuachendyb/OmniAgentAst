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
    timezone_convert,
    timer,
)
from app.services.tools.meta.time_schema import (
    GetTimeInput,
    TimeAddInput,
    TimeDiffInput,
    QueryCalendarInput,
    TimezoneConvertInput,
    TimerInput,
)


META_TOOL_DESCRIPTIONS = {
    "tool_help": """查询指定工具的详细用法信息。

【使用场景】
- 当Agent需要了解某个工具的具体参数和用法时使用
- 当用户问"read_csv怎么用"时使用
- 当需要确认工具是否支持某个参数时使用

【使用示例】
- 查询工具:tool_help(tool_name="get_time")
- 查询用法:tool_help(tool_name="read_csv")

【返回数据说明】
- name: 工具名称
- category: 所属分类
- description: 工具描述
- params: 参数详情(类型、描述、是否必填)
- examples: 使用示例
- version: 版本号
- author: 作者""",
    "tool_search": """按关键词搜索匹配的工具列表。

【使用场景】
- 当用户描述需求但不确定用哪个工具时使用
- 当用户问"有什么工具能读取Excel"时使用
- 当需要发现可用工具时使用

【使用示例】
- 搜索工具:tool_search(query="读取CSV文件")
- 按功能搜索:tool_search(query="时间格式化")

【返回数据说明】
- query: 搜索关键词
- matches: 匹配的工具列表(按相关度排序)
- total_matched: 总匹配数
- total_tools: 工具总数""",
    "pipeline": """定义工具执行管道,将多个工具按顺序编排执行。

【使用场景】
- 当需要连续执行多个工具形成自动化流程时使用
- 当需要"先A→再B→如果失败则C"的执行链时使用
- 当需要减少ReAct循环中的推理步数时使用

【重要】
- steps参数为JSON格式的数组,每个元素包含tool(工具名,必填)和params(参数字典,可选)
- 前一步的输出data会自动注入后一步的params中(核心特性)

【使用示例】
- 单步管道:pipeline(steps='[{"tool":"get_time","params":{"action":"now"}}]', stop_on_error=true)
- 多步管道:pipeline(steps='[{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]')

【返回数据说明】
- total_steps: 总步骤数
- completed_steps: 完成步骤数
- results: 每步执行结果(含step/tool/code/message/data)
- 当某步失败时(若stop_on_error=True)返回ERR_PIPELINE_STOPPED""",
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
    "time_add": """时间加减运算。

【使用场景】
- 计算N天/小时/分钟后的时间
- 计算N天/小时/分钟前的时间(delta传负数)

【使用示例】
- 加7天:time_add(start="2026-05-18 10:00:00", delta=7, unit="days")
- 减3小时:time_add(start="2026-05-18 10:00:00", delta=-3, unit="hours")

【返回数据说明】
- result_time: 计算后的时间字符串
- iso: ISO格式时间
- timestamp: Unix时间戳
- tz: 时区
- unit_used: 实际使用的偏移单位
- delta_used: 实际使用的偏移量
- weekday: 星期名称
- isoweckday: ISO星期编号""",
    "time_diff": """计算两个时间之间的差值。

【使用场景】
- 计算两个日期相差几天/小时/分钟
- 计算距某时间还有多久

【使用示例】
- 计算差值:time_diff(start="2026-05-01", end="2026-05-18")

【返回数据说明】
- humanized: 人类可读的差值描述
- seconds/minutes/hours/days: 各单位的差值
- is_future: 目标时间是否在未来
- is_after/is_before/is_equal: 比较结果
- diff_seconds_signed: 带符号的秒数差值""",
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
    "timezone_convert": """支持时区转换功能。
direction参数决定转换方向:
- utc_to_local: UTC时间→本地时间,time_value(可选tz)
- local_to_utc: 本地时间→UTC时间,time_value(可选tz)
- any: 任意源时区→本地时间,time_value+tz

使用示例:
- UTC转本地 → timezone_convert(time_value="2026-05-18 10:00:00", direction="utc_to_local", tz="Asia/Shanghai")
- 任意时区转换 → timezone_convert(time_value="2026-05-18 10:00:00", direction="any", tz="Asia/Shanghai")""",
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
    "timezone_convert": [
        {"time_value": "2026-05-18 10:00:00", "direction": "utc_to_local", "tz": "Asia/Shanghai"},
        {"time_value": "2026-05-18 10:00:00", "direction": "any", "tz": "Asia/Shanghai"},
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
        "timezone_convert": timezone_convert,
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
        "timezone_convert": TimezoneConvertInput,
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
