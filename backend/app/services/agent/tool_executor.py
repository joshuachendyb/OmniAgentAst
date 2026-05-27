# -*- coding: utf-8 -*-
"""
工具执行器模块

负责执行解析后的工具调用，处理错误和结果格式化
Author: 小沈 - 2026-03-21
Version: 1.1 - 2026-04-19 添加T3重试逻辑
Version: 1.2 - 2026-05-02 添加工具别名映射机制 - 小健
"""

import asyncio
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.utils.error_classifier import ErrorCategory, UnifiedErrorClassifier
from app.services.agent.tool_result_utils import create_tool_result, create_error_tool_result

from app.constants import (
    ERR_MISSING_PARAM,
    ERR_TOOL_DEPRECATED,
    ERR_TOOL_NOT_FOUND,
    ERR_UNKNOWN,
)

# 工具结果格式化 — 小沈 2026-05-21
from app.services.agent.tool_result_formatter import (
    _format_llm_observation,
    _format_frontend_event,
)

# 【步骤7】T2: 从ToolConfig加载超时和别名
from app.services.tools.tool_config import (
    get_tool_config,
    get_tool_name_alias,
    is_deprecated_tool,


)


# =============================================================================
# 7.4.3 T3：执行器增强 - 重试（错误分类已迁移到 app.utils.error_classifier）
# =============================================================================

# 工具超时配置 - 从tool_meta.py统一导入 - 小健 2026-05-02
from app.services.tools.tool_meta import TOOL_TIMEOUTS, get_timeout



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
        步骤5：增加别名转换和废弃检查 - 小健 2026-05-02
        
        Args:
            action: 工具名称
            action_input: 工具参数
        
        Returns:
            执行结果，包含success标志和结果数据
        """
        # 【废弃检查】小健 2026-05-02
        deprecation_msg = is_deprecated_tool(action)
        if deprecation_msg:
            return {
                "code": ERR_TOOL_DEPRECATED,
                "data": None,
                "message": f"工具 '{action}' 已废弃: {deprecation_msg}",
                "retry_count": 0
            }
        
        # 【别名转换】小健 2026-05-02
        original_action = action
        main_name = get_tool_name_alias(action)
        if main_name:
            action = main_name
            logger.info(f"工具别名转换: {original_action} -> {action}")
        
        if action == "finish":
            return create_tool_result(
                code="SUCCESS",
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

    @staticmethod
    def _build_retry_error(
        code: str, message: str, retry_count: int,
        *, error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """统一构建重试相关错误响应（21.5 组件1，小沈 2026-05-25 实施）
        
        消除 4 处重复 {code, data, message, retry_count, metadata} 构建。
        retry_count 统一为"已完成的重试次数"（不含首次尝试）。
        
        Note: 该方法保留用于向后兼容，实际实现已迁移到 tool_retry_engine.py
        """
        result = {
            "code": code, "data": None,
            "message": message, "retry_count": retry_count,
        }
        if error_type:
            result["metadata"] = {"error_type": error_type}
        return result

    async def _execute_with_retry(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """重试执行工具（使用统一重试引擎）
        
        Note: 实际逻辑已迁移到 tool_retry_engine.py
        此方法作为适配器保留，调用统一重试引擎
        """
        from app.services.agent.tool_retry_engine import execute_tool_with_unified_retry
        
        # 使用统一重试引擎执行
        return await execute_tool_with_unified_retry(action, action_input, self.available_tools)
    
    def normalize_params(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        参数规范化：基于tool_registry的input_schema校验 - 小健 2026-05-02

        从tool_registry.get_tool()获取input_schema，支持所有tool类型（file/shell/network等）
        删除硬编码的file_register依赖。

        Args:
            action: 工具名称
            action_input: 原始参数

        Returns:
            规范化后的参数
        """
        params = action_input.copy()
        
        # 从tool_registry获取input_schema，支持所有tool类型
        try:
            from app.services.tools.registry import tool_registry
            metadata = tool_registry.get_tool(action)
            if metadata and metadata.input_schema:
                valid_params = set(metadata.input_schema.get("properties", {}).keys())
                invalid_keys = []
                for key in list(params.keys()):
                    if key not in valid_params:
                        val = params[key]
                        val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                        logger.warning(
                            f"[参数监控] action={action}, 非标准参数名: "
                            f"param={key}={val_str}, 期望参数={sorted(valid_params)}"
                        )
                        invalid_keys.append(key)
                # 【修复 2026-05-07 小沈】删除非法参数，防止传给函数报 unexpected keyword argument
                for key in invalid_keys:
                    del params[key]
        except Exception as e:
            logger.warning(f"[参数监控] action={action}, 获取schema失败: {e}")
        
        return params
