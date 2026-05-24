# -*- coding: utf-8 -*-
"""
工具执行器模块

负责执行解析后的工具调用，处理错误和结果格式化
Author: 小沈 - 2026-03-21
Version: 1.1 - 2026-04-19 添加T3重试逻辑
Version: 1.2 - 2026-05-02 添加工具别名映射机制 - 小健
"""

import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.utils.logger import logger
from app.constants import DEFAULT_RETRYABLE_ERRORS

# 工具结果格式化 — 小沈 2026-05-21
from app.services.agent.tool_result_formatter import (
    _format_llm_observation,
    _format_frontend_event,
)

# 【步骤7】T2: 从ToolConfig加载超时和别名
from app.services.tools.tool_config import (
    get_tool_config,
    get_tool_name_alias,
    is_deprecated_tool
)


# =============================================================================
# 7.4.3 T3：执行器增强 - 错误分类与重试
# =============================================================================

class ErrorType(Enum):
    """错误类型枚举（含is_retryable/to_status/description）"""
    
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    FILE_NOT_FOUND = "file_not_found"
    INVALID_PARAMS = "invalid_params"
    TOOL_NOT_FOUND = "tool_not_found"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"
    
    @property
    def is_retryable(self) -> bool:
        """判断错误是否可重试"""
        return self.value in ["timeout"]
    
    @property
    def to_status(self) -> str:
        """转换为status字符串"""
        mapping = {
            "timeout": "timeout",
            "permission_denied": "permission_denied",
            "file_not_found": "error",
            "invalid_params": "error",
            "tool_not_found": "error",
            "unknown": "error",
        }
        return mapping.get(self.value, "error")
    
    @property
    def description(self) -> str:
        """错误描述"""
        mapping = {
            "timeout": "执行超时",
            "permission_denied": "权限拒绝",
            "file_not_found": "文件未找到",
            "invalid_params": "无效参数",
            "tool_not_found": "工具未找到",
            "unknown": "未知错误",
        }
        return mapping.get(self.value, "未知错误")


class ErrorClassifier:
    """错误分类器"""
    
    @staticmethod
    def classify(error: Exception) -> ErrorType:
        """分类错误类型"""
        error_msg = str(error).lower()
        
        if isinstance(error, asyncio.TimeoutError):
            return ErrorType.TIMEOUT
        elif isinstance(error, PermissionError):
            return ErrorType.PERMISSION_DENIED
        elif isinstance(error, FileNotFoundError):
            return ErrorType.FILE_NOT_FOUND
        elif isinstance(error, ValueError):
            return ErrorType.INVALID_PARAMS
        elif isinstance(error, (KeyError, TypeError, AttributeError)):
            return ErrorType.INVALID_PARAMS
        elif isinstance(error, OSError):
            return ErrorType.FILE_NOT_FOUND
        elif "not found" in error_msg or "does not exist" in error_msg:
            return ErrorType.TOOL_NOT_FOUND
        else:
            return ErrorType.UNKNOWN


class RetryPolicy:
    """重试策略（精简版：无熔断器）"""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        retryable_errors: Optional[List[str]] = None
    ):
        """
        初始化重试策略
        
        Args:
            max_retries: 最大重试次数
            backoff_factor: 退避因子
            retryable_errors: 可重试错误列表
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retryable_errors = retryable_errors or DEFAULT_RETRYABLE_ERRORS


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
            # 【M5修正】从tool_registry获取实现函数 - 【修复 2026-05-10 小健】确保先注册
            from app.services.tools import ensure_tools_registered
            ensure_tools_registered()
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
                "code": "ERR_TOOL_DEPRECATED",
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
            return {
                "code": "SUCCESS",
                "data": action_input.get("result"),
                "message": action_input.get("result", "Task completed"),
                "retry_count": 0
            }
        
        if action not in self.available_tools:
            # 【2026-04-30 小沈】跨分类fallback：本地没有时从全局registry查找
            # 【防御 2026-05-10 小沈】本地映射为空时先确保按需注册已完成（避免首请求时序窗口）
            if not self.available_tools:
                from app.services.tools import ensure_tools_registered
                ensure_tools_registered()
            from app.services.tools.registry import tool_registry
            impl = tool_registry.get_implementation(action)
            if impl is not None:
                self.available_tools[action] = impl
                return await self._execute_with_retry(action, action_input)
            return {
                "code": "ERR_TOOL_NOT_FOUND",
                "data": None,
                "message": f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                "retry_count": 0
            }
        
        # 【步骤4】使用重试逻辑执行
        return await self._execute_with_retry(action, action_input)
    
    async def _execute_with_retry(
        self,
        action: str,
        action_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        步骤5：修改_execute_with_retry()，使用ErrorClassifier统一分类
        """
        tool = self.available_tools[action]
        config = get_tool_config()
        retry_policy = RetryPolicy(
            max_retries=config.get_retry_max(action),
            backoff_factor=config.get_retry_backoff(action),
            retryable_errors=config.get_retryable_errors(action)
        )
        
        attempt_count = 0
        last_error: Optional[Exception] = None
        
        while attempt_count <= retry_policy.max_retries:
            try:
                normalized_input = self._normalize_params(action, action_input)
                
                # 验证必需参数
                import inspect
                sig = inspect.signature(tool)
                required_params = [
                    p.name for p in sig.parameters.values()
                    if p.default == inspect.Parameter.empty
                    and p.name != 'self'
                    and p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
                ]
                missing = [p for p in required_params if p not in normalized_input]
                if missing:
                    logger.warning(f"[参数验证] action={action} 缺少必需参数: {missing}")
                    return {
                        "code": "ERR_MISSING_PARAM",
                        "data": None,
                        "message": f"Missing required parameter(s): {', '.join(missing)}",
                        "retry_count": 0
                    }
                
                # 执行工具
                # 【修复 2026-04-30 小沈】兼容同步工具函数（如execute_shell_command/find_command）
                # 【修复 2026-05-07 小沈】lambda包装的async工具：iscoroutinefunction(lambda)=False，
                # 需要先调用lambda拿到实际方法再判断是否coroutine
                # 【修复 2026-05-10 小健】使用tool_meta.get_timeout（精细配置）替代config.get_timeout（YAML default=5秒太小）
                # 【修复 2026-05-14 小沈】同步工具统一走to_thread线程池，不阻塞主线程事件循环
                # =========================================================================
                # 背景：execute_shell_command/ping/port_check等工具内部用subprocess.run()或
                # socket.socket()等同步阻塞调用。如果直接在事件循环线程执行，会导致整个asyncio
                # 事件循环卡死——SSE无法发送事件、新请求无法处理、服务器僵死。
                # 
                # 修复方案：所有非async def的工具都通过asyncio.to_thread()委托到线程池执行，
                # 释放事件循环继续处理其他协程。
                #
                # 三种工具类型的处理路径：
                #   1. 纯async def工具（iscoroutinefunction=True）：
                #      → 直接await，asyncio.wait_for做超时保护（保持不变）
                #   2. lambda包装的async工具（iscoroutinefunction=False，但调用后返回coroutine）：
                #      → to_thread执行lambda，lambda在子线程中创建coroutine对象
                #      → coroutine返回主线程，await执行真正的async逻辑
                #   3. 纯同步工具（iscoroutinefunction=False，返回值不是coroutine）：
                #      → to_thread在线程池执行，subprocess.run不阻塞事件循环
                #      → asyncio.wait_for做超时保护
                # =========================================================================
                timeout = get_timeout(action)
                if inspect.iscoroutinefunction(tool):
                    result = await asyncio.wait_for(tool(**normalized_input), timeout=timeout)
                else:
                    # 【修复 小健 2026-05-24】P1-8: 区分真同步工具和返回coroutine的async工具
                    # 对于返回coroutine的工具，直接await而非走to_thread
                    _sync_call = tool(**normalized_input)
                    if inspect.iscoroutine(_sync_call):
                        # 返回coroutine的async工具（iscoroutinefunction=False但返回coroutine）
                        result = await asyncio.wait_for(_sync_call, timeout=timeout)
                    else:
                        # 真同步工具：走to_thread避免阻塞事件循环
                        result = await asyncio.wait_for(
                            asyncio.to_thread(lambda: _sync_call),
                            timeout=timeout
                        )
                
                return result
            
            except Exception as e:
                last_error = e
                error_type = ErrorClassifier.classify(e)
                attempt_count += 1
                
                # 步骤5：记录日志
                logger.warning(
                    f"[重试] action={action} 尝试{attempt_count}/{retry_policy.max_retries} "
                    f"失败: {error_type.description} - {str(e)[:100]}"
                )
                
                # 检查是否可重试（is_retryable硬编码timeout + retryable_errors来自config）
                if not (error_type.is_retryable or error_type.value in retry_policy.retryable_errors):
                    return {
                        "code": f"ERR_{error_type.value.upper()}",
                        "data": None,
                        "message": f"{error_type.description}: {str(e)[:200]}",
                        # 【修复 小健 2026-05-24】P2-17: retry_count统一为重试次数(不含首次尝试)
                        "retry_count": attempt_count - 1,
                        "metadata": {"error_type": error_type.value}
                    }
                
                # 检查是否还有重试机会
                if attempt_count >= retry_policy.max_retries:
                    logger.error(f"[重试] action={action} 超过最大重试次数{retry_policy.max_retries}")
                    return {
                        "code": f"ERR_{error_type.value.upper()}",
                        "data": None,
                        "message": f"{error_type.description}: {str(e)[:200]}",
                        "retry_count": attempt_count - 1,
                        "metadata": {"error_type": error_type.value}
                    }
                
                # 等待后重试（指数退避）
                wait_time = retry_policy.backoff_factor ** (attempt_count - 1)
                logger.info(f"[重试] action={action} 等待{wait_time}秒后重试...")
                await asyncio.sleep(wait_time)
        
        # 返回最后的错误
        return {
            "code": "ERR_UNKNOWN",
            "data": None,
            "message": str(last_error)[:200] if last_error else "Unknown error",
            "retry_count": attempt_count
        }
    
    def _normalize_params(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
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
    
