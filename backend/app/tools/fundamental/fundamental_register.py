# -*- coding: utf-8 -*-
"""
FUNDAMENTAL Register — 基础工具注册点

【2026-06-18 小欧】从 meta/ 迁入, 匹配 ToolCategory.FUNDAMENTAL
【2026-07-20 小欧】加描述规范:工具描述保持简洁不冗余,能力详情与默认支持能力只写在 schema 类 docstring,禁止在 register 工具描述里重复
【2026-07-28 北京老陈】timeadd/timediff/calendar 迁至 TIMER 分类; shell 从 SHELL 迁入
【2026-07-30 小沈】searchtool examp加"时间 定时"用例,补全7类备用工具

5个工具:
- searchtool — BM25全文检索搜索工具
- timenow — 获取当前时间
- sysinfo — 获取系统信息 (从SYSTEM迁入)
- notify — 发送系统通知 (从DESKTOP迁入)
- shell — 执行系统命令(ps7/ps5/cmd/bash) (从SHELL迁入)
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

# 基础工具依赖配置 — 小健 2026-06-18
FUNDAMENTAL_TOOL_DEPENDENCIES = {
    "searchtool": [],  # 使用内置库
    "timenow": [],  # 使用内置库
    "shell": [],  # 使用内置库
    "sysinfo": ["psutil"],  # 从SYSTEM迁入
    "notify": ["win10toast"],
}

from app.tools.fundamental.fundamental_schema import (
    ToolSearchInput,
    TimeNowInput,
    ShellInput,
    SendNotificationInput,
    GetSystemInfoInput,
)
from app.tools.fundamental.tool_search import searchtool
from app.tools.fundamental.time_now import timenow
from app.tools.fundamental.execute_shell_command import shell
from app.tools.fundamental.get_system_info import sysinfo
from app.tools.fundamental.send_notification import notify


# 【描述规范】2026-07-20 北京老陈 — 工具描述(本 FUNDAMENTAL_TOOL_DESCRIPTIONS 字典)保持简洁、不冗余:
# 能力详情与默认支持的能力只写在对应 Schema 类的 docstring 里(会进入 JSON Schema 发给 LLM);
# 本字典仅作一句话路由/适用场景说明,严禁重复 schema docstring 内容。
FUNDAMENTAL_TOOL_DESCRIPTIONS = {
    "searchtool": """搜索备用工具。按工具名称和类型关键词检索并自动注入匹配的工具分类。适用场景:当前工具列表无对应的专用工具时使用。""",
    "timenow": """获取当前系统时间,返回ISO格式、时间戳、格式化字符串、时区、星期等信息。适用场景:需要获取当前时间时使用。""",
    "shell": """执行系统命令(ps7/ps5/cmd/bash)。适用场景:需要运行系统命令、执行脚本、启动程序时使用。""",
    "sysinfo": """获取系统信息,包括操作系统、CPU、内存、磁盘和网络。适用场景:需要诊断系统问题(CPU高、内存不足、磁盘满)、了解硬件规格时使用。""",
    "notify": """发送Windows系统通知弹窗。适用场景:需要向用户发送桌面通知时使用。""",
}

FUNDAMENTAL_TOOL_EXAMPLES = {
    "searchtool": [
        {"query": "文档 读写"},
        {"query": "数据分析 图表"},
        {"query": "数据库 SQL"},
        {"query": "网络 搜索 下载"},
        {"query": "系统 进程 注册表 任务"},
        {"query": "桌面 窗口"},
        {"query": "时间 定时"},
    ],
    "timenow": [
        {},
    ],
    "shell": [
        {"command": "dir", "timeout": 10},
        {"command": "python --version", "shell_type": "ps7", "timeout": 10},
        {"command": "ls -la", "shell_type": "bash", "timeout": 10},
        {"command": "Get-ChildItem", "shell_type": "ps5", "timeout": 10},
    ],
    "sysinfo": [
        {},
        {"info_type": "all"},
        {"info_type": "basic"},
        {"info_type": "cpu"},
        {"info_type": "memory"},
        {"info_type": "disk"},
        {"info_type": "network"},
    ],
    "notify": [
        {"title": "AI热点新闻", "message": "已为您搜索到最新AI行业新闻"},
        {"title": "任务完成", "message": "全部操作已完成", "duration": 5},
        {"title": "系统提醒", "message": "这是一条包含特殊字符<>&\"'的通知消息", "duration": 10},
        {"title": "长文本测试标题用于验证通知系统的稳定性", "message": "这是一条较长的通知内容，用于测试系统对长文本的处理能力，确保不会出现截断或显示异常", "duration": 8},
    ],
}


def _register_fundamental_tools():
    """注册5个基础工具到FUNDAMENTAL分类 — 小健 2026-06-18"""
    CONFIRMATION_MAP = {
        "shell": {"write": True},
    }
    
    tool_methods = {
        "searchtool": searchtool,
        "timenow": timenow,
        "shell": shell,
        "sysinfo": sysinfo,
        "notify": notify,
    }

    TOOL_INPUT_MODELS = {
        "searchtool": ToolSearchInput,
        "timenow": TimeNowInput,
        "shell": ShellInput,
        "sysinfo": GetSystemInfoInput,
        "notify": SendNotificationInput,
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
            needs_confirmation=(name == "shell"),
            action_confirmation=CONFIRMATION_MAP.get(name),
            dependencies=FUNDAMENTAL_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(f"[fundamental_register] 已注册工具: {name}, Pydantic模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


__all__ = [
    "_register_fundamental_tools",
    "searchtool",
    "timenow",
    "shell",
    "sysinfo",
    "notify",
]
