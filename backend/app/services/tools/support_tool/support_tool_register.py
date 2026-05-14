# -*- coding: utf-8 -*-
"""
Support Tool Register - 支撑工具显式注册

【架构规范】2026-05-02 小沈
【更新时间】2026-05-14 小健 - 5个数据库事务工具移到database分类

================================================================================
一、注册方式
================================================================================
使用 tool_registry.register() 逐一注册，category=ToolCategory.SUPPORT_TOOL

================================================================================
二、包含工具（2个）
================================================================================
- check_network_connectivity: 检查网络连通性（input_model）
- validate_url: 验证URL格式（input_model）

【注意】2026-05-14 小健：以下5个工具已移到database分类注册：
- check_db_exists → database_register.py
- get_table_schema → database_register.py
- begin_transaction → database_register.py
- commit_transaction → database_register.py
- rollback_transaction → database_register.py

Author: 小沈 - 2026-05-02
"""

import logging

from app.services.tools.registry import tool_registry, ToolCategory
from app.services.tools.support_tool.support_tool_schema import (
    ValidateUrlInput,
    CheckNetworkConnectivityInput,
)
from app.services.tools.support_tool.support_tool_tools import (
    check_network_connectivity,
    validate_url,
)

logger = logging.getLogger(__name__)

DESCRIPTIONS = {
    "check_network_connectivity": """检查网络连通性。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要确认网络是否可用时使用
- 当用户在执行网络操作前需要验证连通性时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"host": "xxx"}  # 不要传任何参数！

返回数据说明：
- code: 状态码(SUCCESS)
- data.connected: 网络是否连通(bool)
- data.host: 连通的测试主机(str，连通时)
- data.latency_ms: 延迟毫秒数(float，连通时)
- message: 结果消息""",

    "validate_url": """验证URL格式是否正确。

使用场景：
- 当用户需要确认URL格式是否有效时使用
- 当用户在发送网络请求前需要验证URL时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.valid: URL是否有效(bool)
- data.scheme: 协议类型(str)
- data.netloc: 网络位置(str)
- data.path: 路径(str)
- data.error: 错误信息(str，异常时)
- message: 结果消息""",
}

EXAMPLES = {
    "check_network_connectivity": [{}],
    "validate_url": [{"url": "https://example.com"}],
}


def _register_support_tool_tools():
    """注册支撑工具 - 小沈 2026-05-02, 小健 2026-05-14移除数据库工具"""

    tools_to_register = [
        ("check_network_connectivity", check_network_connectivity, CheckNetworkConnectivityInput),
        ("validate_url", validate_url, ValidateUrlInput),
    ]

    for name, impl, input_model in tools_to_register:
        examples = EXAMPLES.get(name, [])
        tool_registry.register(
            name=name,
            description=DESCRIPTIONS[name],
            category=ToolCategory.SUPPORT_TOOL,
            implementation=impl,
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[support_tool_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__}, examples: {len(examples)}个"
        )


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = [
    "_register_support_tool_tools",
    "check_network_connectivity",
    "validate_url",
]
