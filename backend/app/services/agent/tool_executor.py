# -*- coding: utf-8 -*-
"""
工具执行器模块

【分层规范 - 小健 2026-05-27】
本文件属于【Agent编排层】，使用 tool_result_utils.py 的 create_xxx 函数
禁止使用 _response.py 的 build_xxx 函数（那是工具层用的）

负责执行解析后的工具调用，处理错误和结果格式化
Author: 小沈 - 2026-03-21
Version: 1.1 - 2026-04-19 添加T3重试逻辑
Version: 1.2 - 2026-05-02 添加工具别名映射机制 - 小健
"""

import asyncio
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.services.agent.agent_utils.tool_result_utils import create_tool_result, create_error_tool_result

from app.constants import (
    ERR_MISSING_PARAM,
    ERR_TOOL_DEPRECATED,
    ERR_TOOL_NOT_FOUND,
    ERR_UNKNOWN,
)

# 工具结果格式化 — 小沈 2026-05-21
from app.services.agent.tool_result_formatter import (
    format_llm_observation,
    _format_frontend_event,
)

# 【步骤7】T2: 从ToolConfig加载超时
from app.services.tools.tool_config import (
    get_tool_config,
)


# =============================================================================
# 7.4.3 T3：执行器增强 - 重试（错误分类已迁移到 app.utils.error_classifier）
# =============================================================================

# 工具超时配置 - 从tool_config.py统一导入 - 小健 2026-05-02
from app.services.tools.tool_config import get_timeout



class ToolExecutor:
    """
    工具执行器
    
    负责执行解析后的工具调用，处理错误和结果格式化
    """
    
    def __init__(self, tools: Dict[str, Callable] = None):
        """
        初始化工具执行器
        
        Args:
            tools: 工具名称到工具函数的映射字典（可选）
            如果未传入，从registry获取
        """
        if tools is not None:
            self.available_tools = tools
        else:
            from app.services.tools.registry import get_implementations_from_registry
            self.available_tools = get_implementations_from_registry()
    
    async def execute(
        self,
        action: str,
        action_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具调用（带重试逻辑）
        
        步骤4：修改execute()方法，增加重试逻辑
        
        Args:
            action: 工具名称
            action_input: 工具参数
        
        Returns:
            执行结果，包含success标志和结果数据
        """
        if action == "finish":
            return create_tool_result(
                data=action_input.get("result"),
                message=action_input.get("result", "Task completed"),
                retry_count=0
            )
        
        if action not in self.available_tools:
            from app.services.tools.registry import tool_registry
            impl = tool_registry.get_implementation(action)
            if impl is not None:
                self.available_tools[action] = impl
                return await self._execute_with_retry(action, action_input)
            return create_error_tool_result(
                code=ERR_TOOL_NOT_FOUND,
                data=None,
                message=f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                retry_count=0,
                error_message=f"工具 '{action}' 未找到",
                error_type="tool_not_found"
            )
        
        # 【步骤4】使用重试逻辑执行
        return await self._execute_with_retry(action, action_input)

    async def _execute_with_retry(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """重试执行工具（使用统一重试引擎）
        
        Note: 实际逻辑已迁移到 tool_retry_engine.py
        此方法作为适配器保留，调用统一重试引擎
        """
        from app.services.agent.tool_retry_engine import execute_tool_with_unified_retry
        
        # 使用统一重试引擎执行
        return await execute_tool_with_unified_retry(action, action_input, self.available_tools)
    
