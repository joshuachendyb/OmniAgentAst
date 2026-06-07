# -*- coding: utf-8 -*-
"""
统一工具重试引擎

小健 - 2026-06-08 修复P2: 全局单例每次重新获取available_tools, 参数删除改WARNING

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
    ERR_TOOL_NOT_FOUND,
    ERR_UNKNOWN,
)


class ToolRetryEngine:
    """统一工具重试引擎 — 每次执行从registry重新获取工具列表"""
    
    def __init__(self):
        pass
    
    def _get_available_tools(self) -> Dict[str, Callable]:
        """每次执行时从registry重新获取(避免单例缓存过期)"""
        from app.services.tools.tool_queries import get_implementations_from_registry
        return get_implementations_from_registry()
    
    async def _execute_tool_once(self, tool: Callable, normalized_input: Dict[str, Any], 
                                timeout: float) -> Any:
        """
        统一单次工具调用
        
        修复:纯同步工具通过 to_thread 移出事件循环,wait_for 超时保护生效。
        
        Args:
            tool: 工具函数
            normalized_input: 规范化后的参数
            timeout: 超时时间(秒)
        
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
        tool: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """统一工具执行方法 (带重试逻辑)"""
        # 1. 查找工具 (每次从registry重新获取)
        available_tools = self._get_available_tools()
        
        if tool is None:
            tool = available_tools.get(action)
            if tool is None:
                from app.services.tools.registry import tool_registry
                tool = tool_registry.get_implementation(action)
                if tool is not None:
                    available_tools[action] = tool
                else:
                    return create_error_tool_result(
                        code=ERR_TOOL_NOT_FOUND,
                        data=None,
                        message=f"Unknown tool: {action}. Available tools: {list(available_tools.keys())}",
                        retry_count=0,
                        error_message=f"工具 '{action}' 未找到",
                        error_type="tool_not_found"
                    )
        
        # 2. 参数验证 — 非法参数WARNING日志+删除
        params = action_input.copy()
        try:
            from app.services.tools.registry import tool_registry
            metadata = tool_registry.get_tool(action)
            if metadata and metadata.input_schema:
                valid_params = set(metadata.input_schema.get("properties", {}).keys())
                for key in list(params.keys()):
                    if key not in valid_params:
                        val_str = str(params[key])[:50] + "..." if len(str(params[key])) > 50 else str(params[key])
                        logger.warning(
                            f"[参数WARNING] action={action}, 删除非标准参数: "
                            f"{key}={val_str} (有效参数: {sorted(valid_params)})"
                        )
                        del params[key]
        except (ImportError, AttributeError) as e:
            logger.warning(f"[参数监控] action={action}, 获取 schema 失败：{e}", exc_info=True)
        
        # 2.2 检查必需参数
        sig = inspect.signature(tool)
        required = [
            p.name for p in sig.parameters.values()
            if p.default == inspect.Parameter.empty
            and p.name != 'self'
            and p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        ]
        missing = [p for p in required if p not in params]
        if missing:
            return create_error_tool_result(
                code=ERR_MISSING_PARAM,
                message=f"Missing required parameter(s): {', '.join(missing)}",
                retry_count=0,
                error_message=f"缺少必需参数：{', '.join(missing)}",
                error_type="invalid_params"
            )
        
        # 3. 执行工具 (带重试)
        max_retries, backoff_factor, retryable_errors, timeout = self._get_retry_config(action)
        
        def _is_tool_retryable(e: Exception) -> bool:
            error_category = UnifiedErrorClassifier.classify(e)
            return error_category.is_retryable or error_category.name.lower() in retryable_errors
        
        engine = RetryEngine(
            max_retries=max_retries,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_factor=backoff_factor,
            retryable_check=_is_tool_retryable,
        )
        
        last_error: Optional[Exception] = None
        
        while engine.attempt_count <= max_retries:
            try:
                result = await self._execute_tool_once(tool, params, timeout)
                return create_tool_result(
                    data=result,
                    message="Tool execution succeeded",
                    retry_count=engine.attempt_count
                )
                
            except Exception as e:
                last_error = e
                error_category = UnifiedErrorClassifier.classify(e)
                attempt = engine.record_attempt()

                logger.warning(
                    f"[重试] action={action} 尝试{attempt}/{max_retries} "
                    f"失败：{error_category.description} - {str(e)[:100]}",
                    exc_info=True
                )
                
                if not _is_tool_retryable(e) or engine.exhausted:
                    return self._build_retry_error(
                        f"ERR_{error_category.name}",
                        f"{error_category.description}: {str(e)[:200]}",
                        attempt - 1, error_type=error_category.name.lower(),
                    )
                
                await asyncio.sleep(engine.current_delay)
        
        return self._build_retry_error(
            ERR_UNKNOWN, str(last_error)[:200] if last_error else "Unknown error",
            engine.attempt_count - 1,
        )


# 全局单例 - 简单点
_tool_retry_engine: Optional[ToolRetryEngine] = None


def _get_tool_retry_engine() -> ToolRetryEngine:
    """获取工具重试引擎(全局单例)"""
    global _tool_retry_engine
    if _tool_retry_engine is None:
        _tool_retry_engine = ToolRetryEngine()
    return _tool_retry_engine