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
        self.retryable_errors = retryable_errors or ["timeout"]


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
                "status": "error",
                "summary": f"工具 '{action}' 已废弃: {deprecation_msg}",
                "data": None,
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
                "status": "success",
                "summary": "Task completed",
                "result": {
                    "operation_type": "finish",
                    "message": action_input.get("result", "Task completed"),
                    "data": action_input
                },
                "data": action_input.get("result"),
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
                "status": "error",
                "summary": f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                "data": None,
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
                        "status": "error",
                        "summary": f"Missing required parameter(s): {', '.join(missing)}",
                        "data": None,
                        "retry_count": 0
                    }
                
                # 执行工具
                # 【修复 2026-04-30 小沈】兼容同步工具函数（如execute_command/change_directory）
                # 【修复 2026-05-07 小沈】lambda包装的async工具：iscoroutinefunction(lambda)=False，
                # 需要先调用lambda拿到实际方法再判断是否coroutine
                # 【修复 2026-05-10 小健】使用tool_meta.get_timeout（精细配置）替代config.get_timeout（YAML default=5秒太小）
                timeout = get_timeout(action)
                if inspect.iscoroutinefunction(tool):
                    result = await asyncio.wait_for(tool(**normalized_input), timeout=timeout)
                else:
                    # 先调用一次看返回值是否为coroutine（lambda包装的async方法）
                    call_result = tool(**normalized_input)
                    if inspect.iscoroutine(call_result):
                        result = await asyncio.wait_for(call_result, timeout=timeout)
                    else:
                        result = call_result
                
                return self._format_result(result, action)
            
            except Exception as e:
                last_error = e
                error_type = ErrorClassifier.classify(e)
                attempt_count += 1
                
                # 步骤5：记录日志
                logger.warning(
                    f"[重试] action={action} 尝试{attempt_count}/{retry_policy.max_retries} "
                    f"失败: {error_type.description} - {str(e)[:100]}"
                )
                
                # 检查是否可重试
                if not error_type.is_retryable:
                    return {
                        "status": error_type.to_status,
                        "summary": f"{error_type.description}: {str(e)[:200]}",
                        "data": None,
                        "retry_count": attempt_count - 1,
                        "metadata": {"error_type": error_type.value}
                    }
                
                # 检查是否还有重试机会
                if attempt_count >= retry_policy.max_retries:
                    logger.error(f"[重试] action={action} 超过最大重试次数{retry_policy.max_retries}")
                    return {
                        "status": error_type.to_status,
                        "summary": f"{error_type.description}: {str(e)[:200]}",
                        "data": None,
                        "retry_count": attempt_count,
                        "metadata": {"error_type": error_type.value}
                    }
                
                # 等待后重试（指数退避）
                wait_time = retry_policy.backoff_factor ** (attempt_count - 1)
                logger.info(f"[重试] action={action} 等待{wait_time}秒后重试...")
                await asyncio.sleep(wait_time)
        
        # 返回最后的错误
        return {
            "status": "error",
            "summary": str(last_error)[:200] if last_error else "Unknown error",
            "data": None,
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
    
    def _format_result(self, result: Any, action: str) -> Dict[str, Any]:
        """
        格式化工具执行结果
        
        【2026-04-16 小沈修改】新增 warning 状态判断逻辑
        
        Args:
            result: 原始执行结果
            action: 工具名称
        
        Returns:
            格式化后的结果
        """
        if isinstance(result, dict):
            # 【2026-04-16 小沈新增】处理工具返回的warning状态
            if result.get("status") == "warning":
                return {
                    "status": "warning",
                    "summary": result.get("summary", "Warning during execution"),
                    "data": result.get("data"),
                    "retry_count": result.get("retry_count", 0)
                }
            elif "status" in result and "summary" in result:
                return {
                    "status": result.get("status", "success"),
                    "summary": result.get("summary", ""),
                    "data": result.get("data"),
                    "retry_count": result.get("retry_count", 0)
                }
            # 【修复 2026-05-01 小沈】先检查code字段（shell工具返回code/data/message格式）
            # 之前只检查success字段，导致execute_command等工具的SUCCESS结果被误判为error
            elif result.get("code") == "SUCCESS":
                # code=SUCCESS但需区分returncode：0=真正成功，非0=有错误输出
                data = result.get("data")
                if isinstance(data, dict) and data.get("returncode", 0) != 0:
                    return {
                        "status": "error",
                        "summary": result.get("message", f"Command exited with code {data.get('returncode')}"),
                        "data": result,
                        "retry_count": 0
                    }
                else:
                    return {
                        "status": "success",
                        "summary": result.get("message", f"Successfully executed {action}"),
                        "data": result,
                        "retry_count": 0
                    }
            elif result.get("code", "").startswith("ERR_"):
                return {
                    "status": "error",
                    "summary": result.get("message", f"Failed to execute {action}"),
                    "data": result,
                    "retry_count": 0
                }
            elif result.get("success", False):
                return {
                    "status": "success",
                    "summary": result.get("message", f"Successfully executed {action}"),
                    "data": result,
                    "retry_count": 0
                }
            else:
                return {
                    "status": "error",
                    "summary": result.get("error", result.get("message", f"Failed to execute {action}")),
                    "data": result,
                    "retry_count": 0
                }
        else:
            return {
                "status": "success",
                "summary": f"Successfully executed {action}",
                "data": result,
                "retry_count": 0
            }