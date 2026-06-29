"""
工具级错误分类器

责任: 专门处理工具执行相关的错误分类
设计原则: 单一职责、简单直接、与系统级错误分类分离

作者: 小欧 - 2026-06-29
"""

import re
from enum import Enum
from typing import Optional, Tuple, Dict, Any


class ToolErrorCategory(Enum):
    """工具错误分类枚举"""
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    FILE_NOT_FOUND = "file_not_found"
    INVALID_PARAMS = "invalid_params"
    TOOL_NOT_FOUND = "tool_not_found"
    NETWORK = "network"
    CONNECT = "connect"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"
    
    @property
    def is_retryable(self) -> bool:
        """判断工具错误是否可重试"""
        retryable_categories = {
            ToolErrorCategory.TIMEOUT,
            ToolErrorCategory.NETWORK,
            ToolErrorCategory.CONNECT,
            ToolErrorCategory.PROTOCOL,
        }
        return self in retryable_categories
    
    @property
    def to_status(self) -> str:
        """转换为状态字符串"""
        mapping = {
            ToolErrorCategory.TIMEOUT: "timeout",
            ToolErrorCategory.PERMISSION_DENIED: "permission_denied",
            ToolErrorCategory.FILE_NOT_FOUND: "error",
            ToolErrorCategory.INVALID_PARAMS: "error",
            ToolErrorCategory.TOOL_NOT_FOUND: "error",
            ToolErrorCategory.NETWORK: "network_error",
            ToolErrorCategory.CONNECT: "connect_error",
            ToolErrorCategory.PROTOCOL: "protocol_error",
            ToolErrorCategory.UNKNOWN: "error",
        }
        return mapping.get(self, "error")
    
    @property
    def description(self) -> str:
        """错误描述"""
        mapping = {
            ToolErrorCategory.TIMEOUT: "执行超时",
            ToolErrorCategory.PERMISSION_DENIED: "权限拒绝",
            ToolErrorCategory.FILE_NOT_FOUND: "文件未找到",
            ToolErrorCategory.INVALID_PARAMS: "无效参数",
            ToolErrorCategory.TOOL_NOT_FOUND: "工具未找到",
            ToolErrorCategory.NETWORK: "网络错误",
            ToolErrorCategory.CONNECT: "连接错误",
            ToolErrorCategory.PROTOCOL: "协议错误",
            ToolErrorCategory.UNKNOWN: "未知错误",
        }
        return mapping.get(self, "未知错误")


# 异常类型到工具错误分类的映射
EXCEPTION_TO_TOOL_ERROR: Dict[str, ToolErrorCategory] = {
    "TimeoutError": ToolErrorCategory.TIMEOUT,
    "asyncio.TimeoutError": ToolErrorCategory.TIMEOUT,
    "PermissionError": ToolErrorCategory.PERMISSION_DENIED,
    "FileNotFoundError": ToolErrorCategory.FILE_NOT_FOUND,
    "ValueError": ToolErrorCategory.INVALID_PARAMS,
    "TypeError": ToolErrorCategory.INVALID_PARAMS,
    "KeyError": ToolErrorCategory.TOOL_NOT_FOUND,
    "AttributeError": ToolErrorCategory.TOOL_NOT_FOUND,
    "ConnectError": ToolErrorCategory.CONNECT,
    "ConnectTimeout": ToolErrorCategory.CONNECT,
    "ReadTimeout": ToolErrorCategory.TIMEOUT,
    "WriteTimeout": ToolErrorCategory.TIMEOUT,
    "PoolTimeout": ToolErrorCategory.TIMEOUT,
    "NetworkError": ToolErrorCategory.NETWORK,
    "ProtocolError": ToolErrorCategory.PROTOCOL,
    "ProxyError": ToolErrorCategory.NETWORK,
    "SSLError": ToolErrorCategory.NETWORK,
    "InvalidURL": ToolErrorCategory.INVALID_PARAMS,
    "TooManyRedirects": ToolErrorCategory.NETWORK,
    "ReadError": ToolErrorCategory.NETWORK,
    # HTTP状态错误应该归类为网络错误
    "HTTPStatusError": ToolErrorCategory.NETWORK,
    "HTTPError": ToolErrorCategory.NETWORK,
}

# 错误关键词到工具错误分类的映射
KEYWORD_TO_TOOL_ERROR: Dict[str, ToolErrorCategory] = {
    "timeout": ToolErrorCategory.TIMEOUT,
    "timed out": ToolErrorCategory.TIMEOUT,
    "time out": ToolErrorCategory.TIMEOUT,
    "permission denied": ToolErrorCategory.PERMISSION_DENIED,
    "access denied": ToolErrorCategory.PERMISSION_DENIED,
    "forbidden": ToolErrorCategory.PERMISSION_DENIED,
    "no such file": ToolErrorCategory.FILE_NOT_FOUND,
    "file not found": ToolErrorCategory.FILE_NOT_FOUND,
    "not found": ToolErrorCategory.FILE_NOT_FOUND,
    "invalid": ToolErrorCategory.INVALID_PARAMS,
    "missing": ToolErrorCategory.INVALID_PARAMS,
    "required": ToolErrorCategory.INVALID_PARAMS,
    "does not exist": ToolErrorCategory.TOOL_NOT_FOUND,
    "no attribute": ToolErrorCategory.TOOL_NOT_FOUND,
    "os error": ToolErrorCategory.PERMISSION_DENIED,  # OSError通常与权限相关
    "io error": ToolErrorCategory.NETWORK,  # IO错误通常与网络/文件系统相关
}


class ToolErrorClassifier:
    """工具错误分类器"""
    
    @staticmethod
    def classify_tool_error(error: Exception) -> ToolErrorCategory:
        """
        分类工具执行异常类型
        
        Args:
            error: 异常对象
            
        Returns:
            ToolErrorCategory枚举值
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # 检查异常类型映射
        if error_type in EXCEPTION_TO_TOOL_ERROR:
            return EXCEPTION_TO_TOOL_ERROR[error_type]
        
        # 检查错误消息关键词
        for keyword, category in KEYWORD_TO_TOOL_ERROR.items():
            if keyword in error_msg:
                return category
        
        return ToolErrorCategory.UNKNOWN
    
    @staticmethod
    def get_tool_error_info(error: Exception) -> Dict[str, Any]:
        """
        获取工具错误的完整信息
        
        Args:
            error: 异常对象
            
        Returns:
            包含错误分类、消息、是否可重试等信息的字典
        """
        category = ToolErrorClassifier.classify_tool_error(error)
        
        return {
            "category": category,
            "retryable": category.is_retryable,
            "status": category.to_status,
            "description": category.description,
            "original_error": str(error),
            "error_type": type(error).__name__,
        }