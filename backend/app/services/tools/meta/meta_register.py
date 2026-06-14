# -*- coding: utf-8 -*-
"""
Meta Register - 元工具注册点

【2026-05-17 小沈】新建
【2026-06-12 小沈】删除tool_help/pipeline(YAGNI,FC Schema已覆盖),仅保留tool_search+时间工具
"""

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.meta.meta_schema import (
    ToolSearchInput,
)
from app.services.tools.meta.meta_tools import (
    tool_search,
)
from app.services.tools.meta.time_tools import (
    time_now,
    time_add,
    time_diff,
    query_calendar,
    timer,
)
from app.services.tools.meta.time_schema import (
    TimeNowInput,
    TimeAddInput,
    TimeDiffInput,
    QueryCalendarInput,
    TimerInput,
)


META_TOOL_DESCRIPTIONS = {
    "tool_search": """搜索并注入未加载的工具。当当前已加载工具列表中无直接匹配用户需求的工具时,请第一时间调用此工具(不要绕路手写代码读文件/查源码)。按关键词在全部50+工具中做BM25全文检索,返回按相关度排序的工具列表,并自动将匹配的工具分类注入到可用工具列表中。
使用建议:
- 输入1-3个核心功能关键词(如"读取Word文档" "SQL查询" "生成图表" "系统信息")
- 先搜核心动词+名词组合,缩小范围后再补充细节
- 搜不到预期结果时换同义词再试一次
适用场景:所有需要文件操作/SQL查询/图表生成/网络请求/系统管理等能力,但当前工具列表中未找到对应工具的场合。""",
    "time_now": """支持时间获取/格式化/转换操作功能。
action参数决定操作类型:
- now: 获取当前时间(可选format/timezone)
- format: 格式化时间,time_value(可选format)
- to_timestamp: 时间字符串→Unix时间戳,time_value
- from_timestamp: Unix时间戳→时间字符串,time_value(可选target_tz)

使用示例:
- 当前时间 → time_now(action="now")
- 转时间戳 → time_now(action="to_timestamp", time_value="2026-05-18 10:00:00")
- 格式化 → time_now(action="format", time_value="2026-05-18 10:00:00", format="%Y年%m月%d日")""",
    "time_add": """时间加减运算。支持按天/小时/分钟/秒/月进行偏移计算。delta为正数表示N个单位后的时间,delta为负数表示N个单位前的时间。返回计算后的时间字符串、ISO格式、Unix时间戳和星期信息。适用场景:需要计算N天/小时/分钟后的时间、计算某个时间点之前的时间时使用。""",
    "time_diff": """计算两个时间之间的差值。返回人类可读的差值描述以及秒/分钟/小时/天各单位的差值。可判断目标时间是否在未来/过去/相等。适用场景:需要计算两个日期相差几天、计算距某时间还有多久时使用。""",
    "query_calendar": """按节日名称查询日期和假期信息(推荐优先使用name参数)。
name参数: 输入节日名称(如"端午节""春节""中秋""国庆")，一次性返回日期、星期、是否节假日/工作日等全部属性，无需再逐个日期重复查询。
支持:端午节/春节/中秋节/元旦/国庆节/劳动节/清明节/元宵节/七夕节/重阳节/除夕等。
设置name时date和check_type被忽略。首次name查询已包含全部信息，不要再对同一节日逐个日期重复调用。

如不使用name，也可按日期检查:
- weekend: 判断是否为周末,date
- holiday: 判断是否为节假日,date
- workday: 判断是否为工作日,date
- next_workday: 计算下N个工作日,date(可选n)

使用示例(推荐):
- 节日查询 → query_calendar(name="端午节", year=2026)
- 节日查询 → query_calendar(name="春节", year=2026)

使用示例(按日期):
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
    "tool_search": [
        {"query": "读取Word文档"},
        {"query": "SQL查询 数据库"},
        {"query": "生成图表 可视化"},
        {"query": "搜索文件 内容查找"},
        {"query": "系统信息 进程"},
        {"query": "压缩解压 归档"},
    ],
    "time_now": [
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
        {"name": "端午节", "year": 2026},
        {"name": "中秋节", "year": 2026},
    ],
    "timer": [
        {"action": "set", "delay": 180, "callback": "提醒用户喝水"},
        {"action": "list"},
    ],
}


def _register_meta_tools():
    """注册所有Meta工具(含Time迁入工具) — 小沈 2026-06-12 精简"""
    tool_methods = {
        "tool_search": tool_search,
        "time_now": time_now,
        "time_add": time_add,
        "time_diff": time_diff,
        "query_calendar": query_calendar,
        "timer": timer,
    }

    TOOL_INPUT_MODELS = {
        "tool_search": ToolSearchInput,
        "time_now": TimeNowInput,
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
