# -*- coding: utf-8 -*-
"""
Meta Register - 元工具注册点

【2026-05-17 小沈】新建：精简方案13.12节
- tool_help: 查询工具详细用法
- tool_search: 按关键词搜索工具
"""

from app.services.tools.registry import tool_registry, ToolCategory
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
    check_date,
    timezone_convert,
    timer,
)
from app.services.tools.meta.time_schema import (
    GetTimeInput,
    TimeAddInput,
    TimeDiffInput,
    CheckDateInput,
    TimezoneConvertInput,
    TimerInput,
)


META_TOOL_DESCRIPTIONS = {
    "tool_help": """查询指定工具的详细用法信息。

使用场景：
- 当Agent需要了解某个工具的具体参数和用法时使用
- 当用户问"read_csv怎么用"时使用
- 当需要确认工具是否支持某个参数时使用

返回数据说明：
- name: 工具名称
- category: 所属分类
- description: 工具描述
- params: 参数详情（类型、描述、是否必填）
- examples: 使用示例
- version: 版本号
- author: 作者""",
    "tool_search": """按关键词搜索匹配的工具列表。

使用场景：
- 当用户描述需求但不确定用哪个工具时使用
- 当用户问"有什么工具能读取Excel"时使用
- 当需要发现可用工具时使用

返回数据说明：
- query: 搜索关键词
- matches: 匹配的工具列表（按相关度排序）
- total_matched: 总匹配数
- total_tools: 工具总数""",
    "pipeline": """定义工具执行管道，将多个工具按顺序编排执行。

使用场景：
- 当需要连续执行多个工具形成自动化流程时使用
- 当需要"先A→再B→如果失败则C"的执行链时使用
- 当需要减少ReAct循环中的推理步数时使用

【重要】steps参数为JSON格式的数组，每个元素包含tool(工具名)和params(参数字典)

返回数据说明：
- total_steps: 总步骤数
- completed_steps: 完成步骤数
- results: 每步执行结果(含code/message/data)
- 当某步失败时(若stop_on_error=True)返回ERR_PIPELINE_STOPPED""",
}

META_TOOL_EXAMPLES = {
    "tool_help": [
        {"tool_name": "get_current_time"},
        {"tool_name": "read_csv"},
        {"tool_name": "search_files"},
    ],
    "tool_search": [
        {"query": "读取CSV文件"},
        {"query": "查找重复文件"},
        {"query": "时间格式化"},
    ],
    "pipeline": [
        {"steps": '[{"tool":"get_current_time","params":{}}]', "stop_on_error": True},
        {"steps": '[{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]'},
    ],
    # 【2026-05-18 小沈】Time工具示例
    "get_time": [
        {"action": "now"},
        {"action": "to_timestamp", "datetime_str": "2026-05-18 10:00:00"},
    ],
    "time_add": [
        {"datetime_str": "2026-05-18 10:00:00", "days": 7},
    ],
    "time_diff": [
        {"start_time": "2026-05-01", "end_time": "2026-05-18"},
    ],
    "check_date": [
        {"datetime_str": "2026-05-18", "check_type": "weekend"},
    ],
    "timezone_convert": [
        {"datetime_str": "2026-05-18 10:00:00", "from_tz": "Asia/Shanghai", "to_tz": "UTC"},
    ],
    "timer": [
        {"action": "set", "delay": 180, "callback": "提醒用户喝水"},
        {"action": "list"},
    ],
}


def _register_meta_tools():
    """
    【2026-05-18 小沈】注册所有Meta工具（含Time迁入工具）
    """
    tool_methods = {
        "tool_help": tool_help,
        "tool_search": tool_search,
        "pipeline": pipeline,
        "get_time": get_time,
        "time_add": time_add,
        "time_diff": time_diff,
        "check_date": check_date,
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
        "check_date": CheckDateInput,
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
            category=ToolCategory.META,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[meta_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


__all__ = ["_register_meta_tools"]
