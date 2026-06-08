# -*- coding: utf-8 -*-
"""
统一工具重试引擎

小沈 - 2026-06-08 P1-7/8/9: 参数非法改报错, 删全局单例改Agent实例变量, 合并tool_executor重复查找

【分层规范 - 小健 2026-05-27】
本文件属于【Agent编排层】,使用 tool_result_utils.py 的 create_xxx 函数
禁止使用 _response.py 的 build_xxx 函数(那是工具层用的)

负责统一处理工具执行的重试逻辑,消除双重实现
Author: 小沈 - 2026-05-27
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.utils.error_classifier import UnifiedErrorClassifier
from app.utils.retry_engine import RetryEngine, BackoffStrategy
from app.services.tools.tool_constants import TOOL_TIMEOUTS, TOOL_RETRY_MAX, TOOL_RETRY_BACKOFF, TOOL_RETRYABLE_ERRORS
from app.services.agent.agent_utils.tool_result_factory import create_tool_result, create_error_tool_result

from app.constants import (
    ERR_MISSING_PARAM,
    ERR_INVALID_PARAMS,
    ERR_TOOL_NOT_FOUND,
    ERR_UNKNOWN,
)


class ToolRetryEngine:
    """统一工具重试引擎 — 绑定Agent的工具字典"""
    
    def __init__(self, tools: Dict[str, Callable]):
        self._tools = tools
    
    def _is_async_tool(self, tool: Callable) -> bool:
        """判断是否异步工具 — 小沈 2026-06-08"""
        return inspect.iscoroutinefunction(tool)
    
    async def _execute_async_tool(self, tool: Callable, params: Dict[str, Any], timeout: float) -> Any:
        """执行异步工具 — 小沈 2026-06-08"""
        return await asyncio.wait_for(tool(**params), timeout=timeout)
    
    async def _execute_sync_tool(self, tool: Callable, params: Dict[str, Any], timeout: float) -> Any:
        """执行同步工具 — 小沈 2026-06-08"""
        result = await asyncio.wait_for(
            asyncio.to_thread(lambda: tool(**params)), timeout=timeout
        )
        if inspect.iscoroutine(result):
            return await asyncio.wait_for(result, timeout=timeout)
        return result
    
    async def _execute_tool_once(self, tool: Callable, normalized_input: Dict[str, Any], 
                                timeout: float) -> Any:
        """
        统一单次工具调用 — 小沈 2026-06-08 重构
        
        修复:纯同步工具通过 to_thread 移出事件循环,wait_for 超时保护生效。
        """
        if self._is_async_tool(tool):
            return await self._execute_async_tool(tool, normalized_input, timeout)
        return await self._execute_sync_tool(tool, normalized_input, timeout)
    
    def _build_retry_error(
        self, code: str, message: str, retry_count: int,
        *, error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        统一构建重试相关错误响应
        
        消除 4 处重复 {code, data, message, retry_count, metadata} 构建。
        retry_count 统一为"已完成的重试次数"(不含首次尝试)。
        """
        return create_error_tool_result(
            code=code,
            data=None,
            message=message,
            retry_count=retry_count,
            error_message=message,
            error_type=error_type or "unknown"
        )
    
    def _get_retry_config(self, action: str):
        """获取重试配置 — 提取自 execute_tool_with_retry 小健 2026-05-31"""
        return (
            TOOL_RETRY_MAX.get(action, TOOL_RETRY_MAX["default"]),
            TOOL_RETRY_BACKOFF.get(action, TOOL_RETRY_BACKOFF["default"]),
            TOOL_RETRYABLE_ERRORS.get(action, TOOL_RETRYABLE_ERRORS["default"]),
            TOOL_TIMEOUTS.get(action, TOOL_TIMEOUTS["default"]),
        )
    
    async def execute_tool_with_retry(
        self,
        action: str,
        action_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """统一工具执行方法（单一入口，委托给私有方法）
        
        【修复P1-2 2026-06-08 小沈】拆分为私有方法，遵守SRP原则
        """
        if action == "finish":
            return self._handle_finish(action_input)
        
        tool = self._find_tool(action)
        if tool is None:
            return create_error_tool_result(
                code=ERR_TOOL_NOT_FOUND, data=None,
                message=f"Unknown tool: {action}. Available tools: {list(self._tools.keys())}",
                retry_count=0, error_message=f"工具 '{action}' 未找到", error_type="tool_not_found"
            )
        
        params = self._validate_params(action, action_input, tool)
        if params is None:
            return params
        
        return await self._execute_with_retry(action, params, tool)
    
    def _handle_finish(self, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """处理finish短路"""
        return create_tool_result(
            data=action_input.get("result"),
            message=action_input.get("result", "Task completed"),
            retry_count=0
        )
    
    def _find_tool(self, action: str) -> Optional[Callable]:
        """查找工具"""
        tool = self._tools.get(action)
        if tool is None:
            from app.services.tools.registry import tool_registry
            tool = tool_registry.get_implementation(action)
            if tool is not None:
                self._tools[action] = tool
        return tool
    
    def _check_invalid_params(self, action: str, params: Dict[str, Any]) -> bool:
        """检查非法参数 — 小沈 2026-06-08"""
        try:
            from app.services.tools.registry import tool_registry
            metadata = tool_registry.get_tool(action)
            if metadata and metadata.input_schema:
                valid_params = set(metadata.input_schema.get("properties", {}).keys())
                invalid_keys = [k for k in params if k not in valid_params]
                if invalid_keys:
                    return False
        except (ImportError, AttributeError) as e:
            logger.warning(f"[参数监控] action={action}, 获取 schema 失败：{e}", exc_info=True)
        return True
    
    def _check_missing_params(self, tool: Callable, params: Dict[str, Any]) -> bool:
        """检查缺失参数 — 小沈 2026-06-08"""
        sig = inspect.signature(tool)
        required = [
            p.name for p in sig.parameters.values()
            if p.default == inspect.Parameter.empty
            and p.name != 'self'
            and p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        ]
        missing = [p for p in required if p not in params]
        return len(missing) == 0
    
    def _validate_params(self, action: str, action_input: Dict[str, Any], tool: Callable) -> Optional[Dict[str, Any]]:
        """验证参数（非法参数+必需参数）— 小沈 2026-06-08 重构"""
        params = action_input.copy()
        
        if not self._check_invalid_params(action, params):
            return None
        
        if not self._check_missing_params(tool, params):
            return None
        
        return params
    
    def _should_retry(self, e: Exception, retryable_errors: list, engine: RetryEngine) -> bool:
        """判断是否应该重试 — 小沈 2026-06-08"""
        error_category = UnifiedErrorClassifier.classify_error(e)
        is_retryable = error_category.is_retryable or error_category.name.lower() in retryable_errors
        return is_retryable and not engine.exhausted
    
    async def _execute_single_attempt(self, tool: Callable, params: Dict[str, Any], timeout: float, 
                                      engine: RetryEngine, max_retries: int, action: str,
                                      retryable_errors: list) -> Optional[Dict[str, Any]]:
        """执行单次尝试 — 小沈 2026-06-08"""
        try:
            result = await self._execute_tool_once(tool, params, timeout)
            return create_tool_result(
                data=result,
                message="Tool execution succeeded",
                retry_count=engine.attempt_count
            )
        except Exception as e:
            error_category = UnifiedErrorClassifier.classify_error(e)
            attempt = engine.record_attempt()

            logger.warning(
                f"[重试] action={action} 尝试{attempt}/{max_retries} "
                f"失败：{error_category.description} - {str(e)[:100]}",
                exc_info=True
            )
            
            if not self._should_retry(e, retryable_errors, engine):
                return self._build_retry_error(
                    f"ERR_{error_category.name}",
                    f"{error_category.description}: {str(e)[:200]}",
                    attempt - 1, error_type=error_category.name.lower(),
                )
            
            await asyncio.sleep(engine.current_delay)
            return None
    
    async def _execute_with_retry(self, action: str, params: Dict[str, Any], tool: Callable) -> Dict[str, Any]:
        """带重试执行工具 — 小沈 2026-06-08 重构"""
        max_retries, backoff_factor, retryable_errors, timeout = self._get_retry_config(action)
        
        def _is_tool_retryable(e: Exception) -> bool:
            error_category = UnifiedErrorClassifier.classify_error(e)
            return error_category.is_retryable or error_category.name.lower() in retryable_errors
        
        engine = RetryEngine(
            max_retries=max_retries,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_factor=backoff_factor,
            retryable_check=_is_tool_retryable,
        )
        
        last_error: Optional[Exception] = None
        
        while engine.attempt_count <= max_retries:
            result = await self._execute_single_attempt(
                tool, params, timeout, engine, max_retries, action, retryable_errors
            )
            if result is not None:
                return result
        
        return self._build_retry_error(
            ERR_UNKNOWN, str(last_error)[:200] if last_error else "Unknown error",
            engine.attempt_count - 1,
        )

