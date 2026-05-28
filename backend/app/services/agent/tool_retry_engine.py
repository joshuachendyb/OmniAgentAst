# -*- coding: utf-8 -*-
"""
统一工具重试引擎

【分层规范 - 小健 2026-05-27】
本文件属于【Agent编排层】，使用 tool_result_utils.py 的 create_xxx 函数
禁止使用 _response.py 的 build_xxx 函数（那是工具层用的）

负责统一处理工具执行的重试逻辑，消除双重实现
Author: 小沈 - 2026-05-27
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.utils.error_classifier import ErrorCategory, UnifiedErrorClassifier
from app.services.tools.tool_config import get_tool_config, get_timeout
from app.services.agent.agent_utils.tool_result_utils import create_tool_result, create_error_tool_result

from app.constants import (
    ERR_MISSING_PARAM,
    ERR_TOOL_DEPRECATED,
    ERR_TOOL_NOT_FOUND,
    ERR_UNKNOWN,
)


class ToolRetryEngine:
    """
    统一工具重试引擎
    
    合并 tool_executor.py 和 retry_policy.py 中的重试逻辑
    提供统一的工具执行和重试接口
    """
    
    def __init__(self, tools: Dict[str, Callable] = None):
        """
        初始化工具重试引擎
        
        Args:
            tools: 工具名称到工具函数的映射字典（可选）
            如果未传入，从registry获取
        """
        if tools is not None:
            self.available_tools = tools
        else:
            from app.services.tools.registry import get_implementations_from_registry
            self.available_tools = get_implementations_from_registry()
    
    def normalize_params(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        参数规范化：基于tool_registry的input_schema校验
        
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
                # 删除非法参数，防止传给函数报 unexpected keyword argument
                for key in invalid_keys:
                    del params[key]
        except Exception as e:
            logger.warning(f"[参数监控] action={action}, 获取schema失败: {e}")
        
        return params
    
    async def _execute_tool_once(self, tool: Callable, normalized_input: Dict[str, Any], 
                               timeout: float) -> Any:
        """
        统一单次工具调用
        
        修复：纯同步工具通过 to_thread 移出事件循环，wait_for 超时保护生效。
        
        Args:
            tool: 工具函数
            normalized_input: 规范化后的参数
            timeout: 超时时间（秒）
        
        Returns:
            工具执行结果
        """
        if inspect.iscoroutinefunction(tool):
            return await asyncio.wait_for(tool(**normalized_input), timeout=timeout)

        result = await asyncio.wait_for(
            asyncio.to_thread(lambda: tool(**normalized_input)), timeout=timeout
        )
        if inspect.iscoroutine(result):
            return await asyncio.wait_for(result, timeout=timeout)
        return result
    
    def _build_retry_error(
        self, code: str, message: str, retry_count: int,
        *, error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        统一构建重试相关错误响应
        
        消除 4 处重复 {code, data, message, retry_count, metadata} 构建。
        retry_count 统一为"已完成的重试次数"（不含首次尝试）。
        """
        return create_error_tool_result(
            code=code,
            data=None,
            message=message,
            retry_count=retry_count,
            error_message=message,
            error_type=error_type or "unknown"
        )
    
    async def execute_tool_with_retry(
        self,
        action: str,
        action_input: Dict[str, Any],
        tool: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        统一工具执行方法（带重试逻辑）
        
        Args:
            action: 工具名称
            action_input: 工具参数
            tool: 可选传入的工具函数，如果为None则从available_tools获取
        
        Returns:
            执行结果字典
        """
        # 获取工具函数
        if tool is None:
            tool = self.available_tools.get(action)
            if tool is None:
                # 尝试从registry获取
                from app.services.tools.registry import tool_registry
                impl = tool_registry.get_implementation(action)
                if impl is not None:
                    self.available_tools[action] = impl
                    tool = impl
                else:
                    return {
                        "code": ERR_TOOL_NOT_FOUND,
                        "data": None,
                        "message": f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                        "retry_count": 0
                    }
        
        # 检查参数
        sig = inspect.signature(tool)
        required = [
            p.name for p in sig.parameters.values()
            if p.default == inspect.Parameter.empty
            and p.name != 'self'
            and p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        ]
        normalized_input = self.normalize_params(action, action_input)
        missing = [p for p in required if p not in normalized_input]
        if missing:
            return create_error_tool_result(
                code=ERR_MISSING_PARAM,
                message=f"Missing required parameter(s): {', '.join(missing)}",
                retry_count=0,
                error_message=f"缺少必需参数: {', '.join(missing)}",
                error_type="invalid_params"
            )
        
        # 获取重试配置
        config = get_tool_config()
        max_retries = config.get_retry_max(action)
        backoff_factor = config.get_retry_backoff(action)
        retryable_errors = config.get_retryable_errors(action)
        timeout = get_timeout(action)
        
        # 执行重试循环
        attempt_count = 0
        last_error: Optional[Exception] = None
        
        while attempt_count <= max_retries:
            try:
                result = await self._execute_tool_once(tool, normalized_input, timeout)
                return create_tool_result(
                    data=result,
                    message="Tool execution succeeded",
                    retry_count=attempt_count
                )
                
            except Exception as e:
                last_error = e
                error_category = UnifiedErrorClassifier.classify(e)
                attempt_count += 1
                
                logger.warning(
                    f"[重试] action={action} 尝试{attempt_count}/{max_retries} "
                    f"失败: {error_category.description} - {str(e)[:100]}"
                )
                
                if not (error_category.is_retryable or error_category.name.lower() in retryable_errors):
                    return self._build_retry_error(
                        f"ERR_{error_category.name}",
                        f"{error_category.description}: {str(e)[:200]}",
                        attempt_count - 1, error_type=error_category.name.lower(),
                    )
                
                if attempt_count >= max_retries:
                    return self._build_retry_error(
                        f"ERR_{error_category.name}",
                        f"{error_category.description}: {str(e)[:200]}",
                        attempt_count - 1, error_type=error_category.name.lower(),
                    )
                
                await asyncio.sleep(backoff_factor ** (attempt_count - 1))
        
        return self._build_retry_error(
            ERR_UNKNOWN, str(last_error)[:200] if last_error else "Unknown error",
            attempt_count - 1,
        )


# 全局实例
_tool_retry_engine: Optional[ToolRetryEngine] = None


def get_tool_retry_engine() -> ToolRetryEngine:
    """
    获取工具重试引擎单例
    
    Returns:
        ToolRetryEngine实例
    """
    global _tool_retry_engine
    if _tool_retry_engine is None:
        _tool_retry_engine = ToolRetryEngine()
    return _tool_retry_engine


async def execute_tool_with_unified_retry(
    action: str,
    action_input: Dict[str, Any],
    tools: Optional[Dict[str, Callable]] = None,
) -> Dict[str, Any]:
    """
    统一工具执行接口（使用新的重试引擎）
    
    这是对外暴露的统一入口，替换 tool_executor.execute 和 retry_policy.execute_with_retry
    
    Args:
        action: 工具名称
        action_input: 工具参数
        tools: 可选的工具字典
    
    Returns:
        执行结果字典
    """
    engine = get_tool_retry_engine()
    return await engine.execute_tool_with_retry(action, action_input, tools.get(action) if tools else None)