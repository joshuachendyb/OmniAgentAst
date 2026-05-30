# -*- coding: utf-8 -*-
"""
Agent层公共工具函数目录

【公共函数规范】
本目录是Agent层的公共utility模块，所有Agent层公共函数必须在此目录下定义。
禁止在业务代码中重复定义公共函数。
调用方统一从此处导入：from app.services.agent.agent_utils.xxx import yyy

目录结构：
- tool_result_factory.py: 工具结果统一默认值常量 + Agent层结果工厂
- message_utils.py: Message工具函数（纯函数，无状态）
- _utils.py: LLM响应解析器内部工具函数

Author: 小沈 - 2026-05-28
"""

from app.services.agent.agent_utils.tool_result_factory import (
    create_tool_result,
    create_error_tool_result,
    create_warning_tool_result,
)
from app.services.agent.agent_utils.message_utils import (
    build_llm_messages,
    build_observation_text,
    inject_tools_info,
)

__all__ = [
    "create_tool_result",
    "create_error_tool_result",
    "create_warning_tool_result",
    "build_llm_messages",
    "build_observation_text",
    "inject_tools_info",
]
