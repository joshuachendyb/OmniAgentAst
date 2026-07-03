# -*- coding: utf-8 -*-
"""
FUNDAMENTAL Register — 基础工具注册点

【2026-06-18 小欧】从 meta/ 迁入, 匹配 ToolCategory.FUNDAMENTAL

7个工具:
- searchtool — BM25全文检索搜索工具
- time_now — 获取当前时间
- time_add — 时间加减运算
- time_diff — 时间差值计算
- query_calendar — 节日/日期查询
- get_system_info — 获取系统信息 (从SYSTEM迁入)
- send_notification — 发送系统通知 (从DESKTOP迁入)
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 基础工具依赖配置 — 小健 2026-06-18
FUNDAMENTAL_TOOL_DEPENDENCIES = {
    "searchtool": [],  # 使用内置库
    "time_now": [],  # 使用内置库
    "time_add": [],  # 使用内置库
    "time_diff": [],  # 使用内置库
    "query_calendar": [],  # 使用内置库
    "get_system_info": ["psutil"],  # 从SYSTEM迁入
    "send_notification": ["win10toast"],
}

from app.tools.fundamental.fundamental_schema import (
    ToolSearchInput,
    TimeNowInput,
    TimeAddInput,
    TimeDiffInput,
    QueryCalendarInput,
    SendNotificationInput,
    GetSystemInfoInput,
)
from app.tools.fundamental.tool_search import searchtool
from app.tools.fundamental.time_now import time_now
from app.tools.fundamental.time_add import time_add
from app.tools.fundamental.time_diff import time_diff
from app.tools.fundamental.query_calendar import query_calendar
from app.tools.fundamental.get_system_info import get_system_info
from app.tools.fundamental.send_notification import send_notification


FUNDAMENTAL_TOOL_DESCRIPTIONS = {
    "searchtool": """搜索并注入未加载的工具。当前工具列表无匹配时优先调用此工具,按关键词检索并自动注入匹配的工具分类。适用场景:当前工具列表未找到对应的专用工具时使用。""",
    "time_now": """获取当前系统时间,返回ISO格式、时间戳、格式化字符串、时区、星期等信息。适用场景:需要获取当前时间时使用。""",
    "time_add": """对时间进行加减偏移运算,支持天/小时/分钟/秒/月。适用场景:需要计算N个单位后的时间或某个时间点之前的时间时使用。""",
    "time_diff": """计算两个时间之间的差值。适用场景:需要计算日期差、距离某时间还有多久时使用。""",
    "query_calendar": """查询节日日期和假期信息。适用场景:需要了解节日日期、判断日期类型(周末/节假日/工作日)时使用。""",
    "get_system_info": """获取系统信息,包括操作系统、CPU、内存、磁盘和网络。适用场景:需要诊断系统问题(CPU高、内存不足、磁盘满)、了解硬件规格时使用。""",
    "send_notification": """发送Windows系统通知弹窗。适用场景:需要向用户发送桌面通知时使用。""",
}

FUNDAMENTAL_TOOL_EXAMPLES = {
    "searchtool": [
        {"query": "读取Word文档"},
        {"query": "SQL查询 数据库"},
        {"query": "生成图表 可视化"},
        {"query": "搜索文件 内容查找"},
        {"query": "系统信息 进程"},
        {"query": "压缩解压 归档"},
    ],
    "time_now": [
        {},

    ],
    "time_add": [
        {"delta": 7},
        {"delta": 7, "unit": "days"},
        {"delta": 3, "unit": "hours"},
        {"delta": 30, "unit": "minutes"},
        {"delta": 90, "unit": "seconds"},
        {"delta": 2, "unit": "months"},
        {"delta": -7, "unit": "days"},
        {"start": "2026-05-18 10:00:00", "delta": 7, "unit": "days"},
    ],
    "time_diff": [
        {"start": "2026-05-01"},
        {"start": "2026-05-01", "end": "2026-05-18"},
        {"start": 1717200000, "end": 1717804800},
    ],
    "query_calendar": [
        {"name": "端午节", "year": 2026},
        {"name": "春节", "year": 2026},
        {"name": "中秋节", "year": 2026},
        {"name": "国庆节", "year": 2026},
        {"name": "元旦", "year": 2026},
        {"name": "2026-05-18"},
        {"name": "2026-06-24"},
    ],
    "get_system_info": [
        {},
        {"info_type": "all"},
        {"info_type": "basic"},
        {"info_type": "cpu"},
        {"info_type": "memory"},
        {"info_type": "disk"},
        {"info_type": "network"},
    ],
    "send_notification": [
        {"title": "AI热点新闻", "message": "已为您搜索到最新AI行业新闻"},
        {"title": "任务完成", "message": "全部操作已完成", "duration": 5},
        {"title": "系统提醒", "message": "这是一条包含特殊字符<>&\"'的通知消息", "duration": 10},
        {"title": "长文本测试标题用于验证通知系统的稳定性", "message": "这是一条较长的通知内容，用于测试系统对长文本的处理能力，确保不会出现截断或显示异常", "duration": 8},
    ],
}


def _register_fundamental_tools():
    """注册7个基础工具到FUNDAMENTAL分类 — 小健 2026-06-18"""
    tool_methods = {
        "searchtool": searchtool,
        "time_now": time_now,
        "time_add": time_add,
        "time_diff": time_diff,
        "query_calendar": query_calendar,
        "get_system_info": get_system_info,
        "send_notification": send_notification,
    }

    TOOL_INPUT_MODELS = {
        "searchtool": ToolSearchInput,
        "time_now": TimeNowInput,
        "time_add": TimeAddInput,
        "time_diff": TimeDiffInput,
        "query_calendar": QueryCalendarInput,
        "get_system_info": GetSystemInfoInput,
        "send_notification": SendNotificationInput,
    }

    for name, method in tool_methods.items():
        desc = FUNDAMENTAL_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = FUNDAMENTAL_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.FUNDAMENTAL,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            dependencies=FUNDAMENTAL_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(f"[fundamental_register] 已注册工具: {name}, Pydantic模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


__all__ = [
    "_register_fundamental_tools",
    "searchtool",
    "time_now",
    "time_add",
    "time_diff",
    "query_calendar",
    "get_system_info",
    "send_notification",
]
