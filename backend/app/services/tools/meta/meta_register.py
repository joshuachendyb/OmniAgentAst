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
    BatchProcessInput,
)

from app.services.tools.meta.meta_tools import (
    tool_help,
    tool_search,
    pipeline,
    batch_process,
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
- 查询工具：tool_help(tool_name="get_time")
- 查询用法：tool_help(tool_name="read_csv")

【返回数据说明】
- name: 工具名称
- category: 所属分类
- description: 工具描述
- params: 参数详情（类型、描述、是否必填）
- examples: 使用示例
- version: 版本号
- author: 作者""",
    "tool_search": """按关键词搜索匹配的工具列表。

【使用场景】
- 当用户描述需求但不确定用哪个工具时使用
- 当用户问"有什么工具能读取Excel"时使用
- 当需要发现可用工具时使用

【使用示例】
- 搜索工具：tool_search(query="读取CSV文件")
- 按功能搜索：tool_search(query="时间格式化")

【返回数据说明】
- query: 搜索关键词
- matches: 匹配的工具列表（按相关度排序）
- total_matched: 总匹配数
- total_tools: 工具总数""",
    "pipeline": """定义工具执行管道，将多个工具按顺序编排执行。

【使用场景】
- 当需要连续执行多个工具形成自动化流程时使用
- 当需要"先A→再B→如果失败则C"的执行链时使用
- 当需要减少ReAct循环中的推理步数时使用

【重要】
- steps参数为JSON格式的数组，每个元素包含tool(工具名,必填)和params(参数字典,可选)
- 前一步的输出data会自动注入后一步的params中（核心特性）

【使用示例】
- 单步管道：pipeline(steps='[{"tool":"get_time","params":{"action":"now"}}]', stop_on_error=true)
- 多步管道：pipeline(steps='[{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]')

【返回数据说明】
- total_steps: 总步骤数
- completed_steps: 完成步骤数
- results: 每步执行结果(含step/tool/code/message/data)
- 当某步失败时(若stop_on_error=True)返回ERR_PIPELINE_STOPPED""",
    "get_time": """时间操作统一入口 - 合并get_current_time + format_time + timestamp_convert功能。

【使用场景】
- 获取当前时间（action="now"）
- 格式化时间字符串（action="format"）
- 时间戳→时间字符串（action="from_timestamp"）
- 时间字符串→时间戳（action="to_timestamp"）

【使用示例】【常用名转换说明】
- 当前时间/get_current_time → get_time(action="now")
- 时间戳转换 → get_time(action="to_timestamp", time_value="2026-05-18 10:00:00")
- 格式化 → get_time(action="format", time_value="2026-05-18 10:00:00", format_str="%Y年%m月%d日")

【返回数据说明】
- iso: ISO格式时间字符串
- timestamp: Unix时间戳（秒）
- format/formatted: 格式化后的时间字符串
- timezone: 时区信息
- weekday: 星期名称
- isoweckday: ISO星期编号(1=周一,7=周日)""",
    "time_add": """时间加减运算。

【使用场景】
- 计算N天/小时/分钟后的时间
- 计算N天/小时/分钟前的时间（delta传负数）

【使用示例】
- 加7天：time_add(start="2026-05-18 10:00:00", delta=7, unit="days")
- 减3小时：time_add(start="2026-05-18 10:00:00", delta=-3, unit="hours")

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
- 计算差值：time_diff(start="2026-05-01", end="2026-05-18")

【返回数据说明】
- humanized: 人类可读的差值描述
- seconds/minutes/hours/days: 各单位的差值
- is_future: 目标时间是否在未来
- is_after/is_before/is_equal: 比较结果
- diff_seconds_signed: 带符号的秒数差值""",
    "query_calendar": """日期综合检查。

【使用场景】
- 判断是否为周末（check_type="weekend"）
- 判断是否为节假日（check_type="holiday"）
- 判断是否为工作日（check_type="workday"）
- 计算下N个工作日（check_type="next_workday"）

【使用示例】【常用名转换说明】
- 检查周末/check_date → query_calendar(date="2026-05-18", check_type="weekend")
- 检查节假日 → query_calendar(date="2026-05-01", check_type="holiday")
- 下个工作日 → query_calendar(date="2026-05-18", check_type="next_workday")

【返回数据说明】
- date/weekday/isoweckday: 日期及星期信息
- is_weekend: 是否周末
- is_holiday: 是否节假日
- holiday_name: 节假日名称（如有）
- is_workday: 是否工作日
- next_workdays/next_workday_first: 下N个工作日（check_type=next_workday时）""",
    "timezone_convert": """时区转换。

【使用场景】
- UTC转本地时间（direction="utc_to_local"，tz=目标时区）
- 本地转UTC（direction="local_to_utc"，tz=源时区）
- 任意源时区转本地（direction="any"，tz=源时区，此时tz必填）

【使用示例】
- UTC转本地：timezone_convert(time_value="2026-05-18 10:00:00", direction="utc_to_local", tz="Asia/Shanghai")
- 任意时区转换：timezone_convert(time_value="2026-05-18 10:00:00", direction="any", tz="Asia/Shanghai")

【返回数据说明】
- utc_to_local: local_time, timezone, utc_original
- local_to_utc: utc_time, iso, timestamp
- any: 目标时区的时间, iso, timestamp""",
    "batch_process": """批量处理文件 - 合并batch_rename + batch_delete + batch_copy功能。按glob模式匹配文件，执行rename/delete/copy操作。默认dry_run=True预览保护，确认后执行。

【使用场景】
- "把所有.txt改成.md"：批量重命名
- "清空所有.log临时文件"：批量删除
- "把所有备份文件拷贝到归档目录"：批量复制

【使用示例】【常用名转换说明】
- 重命名/batch_rename → batch_process(source_pattern="*.txt", action="rename", target_pattern="*.md")
- 删除/batch_delete → batch_process(source_pattern="logs/*.log", action="delete", dry_run=false)
- 复制/batch_copy → batch_process(source_pattern="backup/*.bak", action="copy", target_dir="D:/archive/")

【返回数据说明】
- matched_count: 匹配文件数
- processed_count: 处理文件数
- operations: 操作详情列表""",
    "timer": """定时器管理 - 合并set_timer + clear_timer + list_timers功能。

【使用场景】
- 设置定时提醒（action="set"，delay和callback必填）
- 清除定时器（action="clear"，timer_id必填）
- 列出所有定时器（action="list"）

【使用示例】【常用名转换说明】
- 设置/set_timer → timer(action="set", delay=180, callback="提醒用户喝水")
- 清除/clear_timer → timer(action="clear", timer_id="timer_001")
- 列出/list_timers → timer(action="list")

【返回数据说明】
- set: timer_id, delay, trigger_at, message
- clear: timer_id, cancelled
- list: 定时器数组

【callback说明】支持三种模式：文本消息(记录日志)、URL(httpx回调)、其他内容""",
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
    # 【2026-05-19 小沈】Time工具示例，参数名与time_schema.py对齐
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
    "batch_process": [
        {"source_pattern": "*.txt", "action": "rename", "target_pattern": "*.md", "dry_run": True},
        {"source_pattern": "logs/*.log", "action": "delete", "dry_run": False, "max_files": 100},
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
        "batch_process": batch_process,
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
        "batch_process": BatchProcessInput,
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
            category=ToolCategory.META,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[meta_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


__all__ = ["_register_meta_tools"]
