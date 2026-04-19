# -*- coding: utf-8 -*-
"""
工具执行器模块

负责执行解析后的工具调用，处理错误和结果格式化
Author: 小沈 - 2026-03-21
Version: 1.1 - 2026-04-19 添加T3重试逻辑
"""

import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.utils.logger import logger

# 【步骤7】T2: 从ToolConfig加载超时和别名
from app.services.tools.tool_config import get_tool_config


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


# 【新增 2026-04-16 小沈】工具超时配置
TOOL_TIMEOUTS = {
    # 文件操作类工具
    "read_file": 30,
    "search_file_content": 60,  # 全文搜索（耗时较长）
    "write_file": 30,
    "delete_file": 30,
    "move_file": 30,
    "list_directory": 10,
    "search_files": 30,
    
    # 命令执行类工具
    "execute_command": 120,
    "run_command": 120,
    
    # 快速工具
    "get_current_time": 5,
    "get_system_info": 10,
    
    # 默认超时
    "default": 30
}


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
            # 【M5修正】从tool_registry获取实现函数
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
                    if p.default == inspect.Parameter.empty and p.name != 'self'
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
                timeout = config.get_timeout(action)
                result = await asyncio.wait_for(tool(**normalized_input), timeout=timeout)
                
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
                if attempt_count > retry_policy.max_retries:
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
        参数规范化：处理参数别名映射
        
        【2026-04-18 小沈修复】
        添加参数别名自动映射，解决LLM返回错误参数名的问题
        - path → dir_path (list_directory)
        - path → file_path (read_file, delete_file)
        - file → file_path (read_file, delete_file)
        
        Args:
            action: 工具名称
            action_input: 原始参数
        
        Returns:
            规范化后的参数
        """
        params = action_input.copy()
        
        # 【新增 2026-04-18 小沈】参数别名映射：常见错误参数名 → 正确参数名
        PARAM_ALIASES = {
            "list_directory": {
                "path": "dir_path",
                "directory_path": "dir_path",
                "folder": "dir_path",
            },
            "read_file": {
                "path": "file_path",
                "file": "file_path",
                "filepath": "file_path",
                "file_name": "file_path",
            },
            "delete_file": {
                "path": "file_path",
                "file": "file_path",
                "filepath": "file_path",
                "file_name": "file_path",
            },
            "write_file": {
                "path": "file_path",
                "file": "file_path",
                "filepath": "file_path",
                "file_name": "file_path",
            },
            "move_file": {
                "source": "source_path",
                "src": "source_path",
                "target": "destination_path",
                "dst": "destination_path",
                "dest": "destination_path",
            },
            "search_files": {
                "file": "file_pattern",
                "filename": "file_pattern",
            },
            "search_file_content": {
                "file_pattern": "file_pattern",
                "filename": "file_pattern",
                "file": "file_pattern",
            },
            "generate_report": {
                "output_dir": "output_dir",
                "output_path": "output_dir",
                "path": "output_dir",
            },
        }
        
        # 执行参数别名映射
        if action in PARAM_ALIASES:
            aliases = PARAM_ALIASES[action]
            for wrong_name, correct_name in aliases.items():
                if wrong_name in params and correct_name not in params:
                    logger.info(f"[参数映射] action={action}: '{wrong_name}' → '{correct_name}'")
                    params[correct_name] = params[wrong_name]
                    del params[wrong_name]
        
        # 定义每个工具的标准参数名
        STANDARD_PARAMS = {
            "read_file": ["file_path", "offset", "limit", "encoding"],
            "write_file": ["file_path", "content", "encoding"],
            "delete_file": ["file_path", "recursive"],
            "list_directory": ["dir_path", "recursive", "max_depth"],
            "move_file": ["source_path", "destination_path"],
            "search_files": ["file_pattern", "path", "recursive", "max_depth", "page_token"],
            "search_file_content": ["pattern", "path", "file_pattern", "recursive"],
            "generate_report": ["output_dir"],
        }
        
        # 检查是否有非标准参数名（映射后再次检查）
        if action in STANDARD_PARAMS:
            standard = STANDARD_PARAMS[action]
            for key in list(params.keys()):
                if key not in standard:
                    val = params[key]
                    val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                    logger.warning(
                        f"[参数监控] action={action}, 仍有非标准参数名: "
                        f"param={key}={val_str}, 期望参数={standard}"
                    )
        
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
                    "summary": result.get("error", f"Failed to execute {action}"),
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