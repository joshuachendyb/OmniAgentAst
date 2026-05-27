"""
统一错误分类模块

责任：统一所有错误分类逻辑，消除3处重复实现
设计原则：单一职责、单一入口、集中管理

目前存在的错误分类分散问题：
1. chat_stream/error_handler.py: classify_error函数
2. services/agent/tool_executor.py: ErrorClassifier类
3. 其他地方可能也有错误分类逻辑

本模块将所有错误分类逻辑统一到一处，提供单一入口函数。
"""

import asyncio
import re
from enum import Enum
from typing import Optional, Tuple, Dict, Any


class ErrorCategory(Enum):
    """错误分类枚举"""
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    FILE_NOT_FOUND = "file_not_found"
    INVALID_PARAMS = "invalid_params"
    TOOL_NOT_FOUND = "tool_not_found"
    CIRCUIT_OPEN = "circuit_open"
    NETWORK = "network"
    CONNECT = "connect"
    PROTOCOL = "protocol"
    SERVER = "server"
    API_RATE_LIMIT = "api_error_429"
    API_UNAUTHORIZED = "api_error_401"
    API_FORBIDDEN = "api_error_403"
    API_BAD_REQUEST = "api_error_400"
    UNKNOWN = "unknown"
    EMPTY_RESPONSE = "empty_response"
    IDLE_TIMEOUT = "idle_timeout"
    
    @property
    def is_retryable(self) -> bool:
        """判断错误是否可重试"""
        retryable_categories = {
            ErrorCategory.TIMEOUT,
            ErrorCategory.NETWORK,
            ErrorCategory.CONNECT,
            ErrorCategory.PROTOCOL,
            ErrorCategory.API_RATE_LIMIT,
            ErrorCategory.IDLE_TIMEOUT,
        }
        return self in retryable_categories
    
    @property
    def to_status(self) -> str:
        """转换为状态字符串"""
        mapping = {
            ErrorCategory.TIMEOUT: "timeout",
            ErrorCategory.PERMISSION_DENIED: "permission_denied",
            ErrorCategory.FILE_NOT_FOUND: "error",
            ErrorCategory.INVALID_PARAMS: "error",
            ErrorCategory.TOOL_NOT_FOUND: "error",
            ErrorCategory.CIRCUIT_OPEN: "error",
            ErrorCategory.NETWORK: "network_error",
            ErrorCategory.CONNECT: "connect_error",
            ErrorCategory.PROTOCOL: "protocol_error",
            ErrorCategory.SERVER: "server_error",
            ErrorCategory.API_RATE_LIMIT: "rate_limit",
            ErrorCategory.API_UNAUTHORIZED: "auth_error",
            ErrorCategory.API_FORBIDDEN: "permission_error",
            ErrorCategory.API_BAD_REQUEST: "bad_request",
            ErrorCategory.UNKNOWN: "error",
            ErrorCategory.EMPTY_RESPONSE: "empty_response",
            ErrorCategory.IDLE_TIMEOUT: "idle_timeout",
        }
        return mapping.get(self, "error")
    
    @property
    def description(self) -> str:
        """错误描述"""
        mapping = {
            ErrorCategory.TIMEOUT: "执行超时",
            ErrorCategory.PERMISSION_DENIED: "权限拒绝",
            ErrorCategory.FILE_NOT_FOUND: "文件未找到",
            ErrorCategory.INVALID_PARAMS: "无效参数",
            ErrorCategory.TOOL_NOT_FOUND: "工具未找到",
            ErrorCategory.CIRCUIT_OPEN: "熔断器打开",
            ErrorCategory.NETWORK: "网络错误",
            ErrorCategory.CONNECT: "连接错误",
            ErrorCategory.PROTOCOL: "协议错误",
            ErrorCategory.SERVER: "服务器错误",
            ErrorCategory.API_RATE_LIMIT: "API限流",
            ErrorCategory.API_UNAUTHORIZED: "认证失败",
            ErrorCategory.API_FORBIDDEN: "权限不足",
            ErrorCategory.API_BAD_REQUEST: "请求参数错误",
            ErrorCategory.UNKNOWN: "未知错误",
            ErrorCategory.EMPTY_RESPONSE: "空响应",
            ErrorCategory.IDLE_TIMEOUT: "空闲超时",
        }
        return mapping.get(self, "未知错误")


# HTTP状态码到错误类型的映射
HTTP_STATUS_TO_ERROR_TYPE: Dict[int, ErrorCategory] = {
    400: ErrorCategory.API_BAD_REQUEST,
    401: ErrorCategory.API_UNAUTHORIZED,
    403: ErrorCategory.API_FORBIDDEN,
    429: ErrorCategory.API_RATE_LIMIT,
    500: ErrorCategory.SERVER,
    502: ErrorCategory.SERVER,
    503: ErrorCategory.SERVER,
    504: ErrorCategory.SERVER,
}

# HTTPX异常到错误类型的映射
HTTPX_EXCEPTION_TO_ERROR_TYPE: Dict[str, ErrorCategory] = {
    "ConnectError": ErrorCategory.CONNECT,
    "ConnectTimeout": ErrorCategory.CONNECT,
    "ReadTimeout": ErrorCategory.TIMEOUT,
    "WriteTimeout": ErrorCategory.TIMEOUT,
    "PoolTimeout": ErrorCategory.TIMEOUT,
    "NetworkError": ErrorCategory.NETWORK,
    "ProtocolError": ErrorCategory.PROTOCOL,
    "ProxyError": ErrorCategory.NETWORK,
    "SSLError": ErrorCategory.NETWORK,
    "InvalidURL": ErrorCategory.INVALID_PARAMS,
    "TooManyRedirects": ErrorCategory.NETWORK,
}

# 错误模式匹配条目
PATTERN_ERROR_ENTRIES = [
    {
        "types": ["TimeoutError", "asyncio.TimeoutError"],
        "keywords": ["timeout", "timed out", "time out"],
        "category": ErrorCategory.TIMEOUT,
    },
    {
        "types": ["PermissionError"],
        "keywords": ["permission denied", "access denied", "forbidden"],
        "category": ErrorCategory.PERMISSION_DENIED,
    },
    {
        "types": ["FileNotFoundError"],
        "keywords": ["no such file", "file not found", "not found"],
        "category": ErrorCategory.FILE_NOT_FOUND,
    },
    {
        "types": ["ValueError", "TypeError"],
        "keywords": ["invalid", "missing", "required"],
        "category": ErrorCategory.INVALID_PARAMS,
    },
    {
        "types": ["KeyError", "AttributeError"],
        "keywords": ["not found", "no attribute", "does not exist"],
        "category": ErrorCategory.TOOL_NOT_FOUND,
    },
]

# 错误类型到用户友好消息的映射
ERROR_TYPE_TO_MESSAGE: Dict[ErrorCategory, Tuple[str, str]] = {
    ErrorCategory.TIMEOUT: ("timeout", "请求超时，请稍后重试"),
    ErrorCategory.PERMISSION_DENIED: ("permission_denied", "权限不足，请检查您的权限设置"),
    ErrorCategory.FILE_NOT_FOUND: ("file_not_found", "文件未找到，请检查文件路径"),
    ErrorCategory.INVALID_PARAMS: ("invalid_params", "参数错误，请检查输入参数"),
    ErrorCategory.TOOL_NOT_FOUND: ("tool_not_found", "工具未找到"),
    ErrorCategory.CIRCUIT_OPEN: ("circuit_open", "服务暂时不可用，请稍后重试"),
    ErrorCategory.NETWORK: ("network", "网络连接失败，请检查网络后重试"),
    ErrorCategory.CONNECT: ("connect", "连接失败，请检查网络连接"),
    ErrorCategory.PROTOCOL: ("protocol", "协议错误，请稍后重试"),
    ErrorCategory.SERVER: ("server", "服务器错误，请稍后重试"),
    ErrorCategory.API_RATE_LIMIT: ("api_error_429", "请求过于频繁，请稍后重试"),
    ErrorCategory.API_UNAUTHORIZED: ("api_error_401", "认证失败，请检查API密钥"),
    ErrorCategory.API_FORBIDDEN: ("api_error_403", "权限不足，请检查API权限"),
    ErrorCategory.API_BAD_REQUEST: ("api_error_400", "请求参数错误"),
    ErrorCategory.UNKNOWN: ("unknown", "未知错误，请稍后重试"),
    ErrorCategory.EMPTY_RESPONSE: ("empty_response", "AI未返回有效响应，请重试"),
    ErrorCategory.IDLE_TIMEOUT: ("idle_timeout", "AI响应超时，请稍后重试"),
}


class UnifiedErrorClassifier:
    """统一错误分类器"""
    
    @staticmethod
    def classify_error(error: Exception) -> ErrorCategory:
        """
        分类异常类型
        
        Args:
            error: 异常对象
            
        Returns:
            ErrorCategory枚举值
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # 特殊处理：IdleTimeoutError
        try:
            from app.utils.idle_timeout import IdleTimeoutError
            if isinstance(error, IdleTimeoutError):
                return ErrorCategory.IDLE_TIMEOUT
        except ImportError:
            pass
        
        # 检查HTTPX异常
        if error_type in HTTPX_EXCEPTION_TO_ERROR_TYPE:
            return HTTPX_EXCEPTION_TO_ERROR_TYPE[error_type]
        
        # 检查内置异常类型
        if isinstance(error, asyncio.TimeoutError):
            return ErrorCategory.TIMEOUT
        elif isinstance(error, PermissionError):
            return ErrorCategory.PERMISSION_DENIED
        elif isinstance(error, FileNotFoundError):
            return ErrorCategory.FILE_NOT_FOUND
        elif isinstance(error, (ValueError, TypeError)):
            return ErrorCategory.INVALID_PARAMS
        elif isinstance(error, (KeyError, AttributeError)):
            return ErrorCategory.TOOL_NOT_FOUND
        
        # 检查字符串模式匹配
        for entry in PATTERN_ERROR_ENTRIES:
            if error_type in entry["types"] or \
               any(kw in error_msg for kw in entry["keywords"]):
                return entry["category"]
        
        # 检查HTTP状态码
        for status_code, error_category in HTTP_STATUS_TO_ERROR_TYPE.items():
            if str(status_code) in error_msg:
                return error_category
        
        # 关键词匹配
        msg_lower = error_msg.lower()
        if "rate limit" in msg_lower or "too many requests" in msg_lower or "limit_error" in msg_lower:
            return ErrorCategory.API_RATE_LIMIT
        if "auth" in msg_lower or "unauthorized" in msg_lower:
            return ErrorCategory.API_UNAUTHORIZED
        if "forbidden" in msg_lower:
            return ErrorCategory.API_FORBIDDEN
        
        return ErrorCategory.UNKNOWN
    
    @staticmethod
    def classify_error_message(error_type: str, error_message: str = "") -> Tuple[str, str]:
        """
        根据错误类型字符串分类，获取用户友好的错误信息
        
        Args:
            error_type: 错误类型标识
            error_message: 原始错误信息
            
        Returns:
            (code, message) 元组
        """
        # 首先尝试将错误类型字符串映射到ErrorCategory
        error_type_upper = error_type.upper()
        for category in ErrorCategory:
            if category.value == error_type_upper or category.name == error_type_upper:
                if category in ERROR_TYPE_TO_MESSAGE:
                    code, default_message = ERROR_TYPE_TO_MESSAGE[category]
                    return code, default_message
        
        # 如果没有匹配，返回默认错误
        return 'server', f"服务调用失败: {error_message}"
    
    @staticmethod
    def get_error_info(error: Exception) -> Dict[str, Any]:
        """
        获取错误的完整信息
        
        Args:
            error: 异常对象
            
        Returns:
            包含错误分类、消息、是否可重试等信息的字典
        """
        category = UnifiedErrorClassifier.classify_error(error)
        code, message = UnifiedErrorClassifier.classify_error_message(category.value, str(error))
        
        return {
            "category": category,
            "code": code,
            "message": message,
            "retryable": category.is_retryable,
            "status": category.to_status,
            "description": category.description,
            "original_error": str(error),
            "error_type": type(error).__name__,
        }
    
    @staticmethod
    def is_network_or_api_error(error_message: str) -> Tuple[bool, Optional[str]]:
        """
        判断错误是否为网络/API错误
        
        Args:
            error_message: 错误消息字符串
            
        Returns:
            (is_network, error_type) 元组
        """
        if not error_message:
            return (False, None)
        
        # 检查HTTP状态码
        for match in re.finditer(r'\b(\d{3})\b', error_message):
            code = int(match.group(1))
            if code in HTTP_STATUS_TO_ERROR_TYPE:
                error_category = HTTP_STATUS_TO_ERROR_TYPE[code]
                is_network = (
                    error_category.value.startswith("api_error_") and error_category != ErrorCategory.API_BAD_REQUEST
                    or error_category in [ErrorCategory.NETWORK, ErrorCategory.CONNECT, ErrorCategory.PROTOCOL, ErrorCategory.TIMEOUT]
                )
                return (is_network, error_category.value)
        
        msg_lower = error_message.lower()
        # 关键词匹配
        if "rate limit" in msg_lower or "too many requests" in msg_lower or "limit_error" in msg_lower:
            return (True, ErrorCategory.API_RATE_LIMIT.value)
        if "auth" in msg_lower or "unauthorized" in msg_lower:
            return (False, ErrorCategory.API_UNAUTHORIZED.value)
        if "forbidden" in msg_lower:
            return (False, ErrorCategory.API_FORBIDDEN.value)
        
        return (False, None)


# 便捷函数
def classify_error(error_type: str, error_message: str = "") -> Tuple[str, str]:
    """兼容现有接口"""
    return UnifiedErrorClassifier.classify_error_message(error_type, error_message)


def get_error_info(error: Exception) -> Dict[str, Any]:
    """获取错误的完整信息"""
    return UnifiedErrorClassifier.get_error_info(error)