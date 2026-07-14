"""
【系统层】系统级错误分类器 — 小欧 2026-06-30；小沈 2026-07-05 黑名单重构

责任：专门处理系统层错误分类（LLM通信、HTTP状态码、系统内部错误）。
      与工具层的 ToolErrorClassifier（看异常类型名）完全独立。

设计原则：
  1. 黑名单策略 — 默认SERVER(retryable)，只列不应重试的例外
     （白名单策略必然遗漏 httpx→httpcore→anyio 多层异常类型）
  2. 单一职责、简单直接

文件：app/services/llm/error_classifier.py（系统层专用）
      app/tools/tool_error_classifier.py（工具层专用）

作者: 小欧 - 2026-06-29

编辑历史:
  2026-07-14 小欧 消除裸魔法数429: 引入HTTP_RATE_LIMIT常量供HTTP_STATUS_TO_ERROR_TYPE引用(代码变迁遗留,非功能退化)
"""

import re
from enum import Enum
from typing import Optional, Tuple, Dict, Any

from app.constants import HTTP_RATE_LIMIT

try:
    from app.utils.idle_timeout import IdleTimeoutError
except ImportError:
    IdleTimeoutError = None

try:
    from app.services.llm.core import FCFormatError
except ImportError:
    FCFormatError = None


class SystemErrorCategory(Enum):
    """系统级错误分类枚举"""
    CIRCUIT_OPEN = "circuit_open"
    SERVER = "server"
    UNKNOWN = "unknown"
    EMPTY_RESPONSE = "empty_response"
    IDLE_TIMEOUT = "idle_timeout"
    
    @property
    def is_retryable(self) -> bool:
        """判断系统错误是否可重试"""
        retryable_categories = {
            SystemErrorCategory.IDLE_TIMEOUT,
            SystemErrorCategory.SERVER,
        }
        return self in retryable_categories
    
    @property
    def to_status(self) -> str:
        """转换为状态字符串"""
        mapping = {
            SystemErrorCategory.CIRCUIT_OPEN: "error",
            SystemErrorCategory.SERVER: "server_error",
            SystemErrorCategory.UNKNOWN: "error",
            SystemErrorCategory.EMPTY_RESPONSE: "empty_response",
            SystemErrorCategory.IDLE_TIMEOUT: "idle_timeout",
        }
        return mapping.get(self, "error")
    
    @property
    def description(self) -> str:
        """错误描述"""
        mapping = {
            SystemErrorCategory.CIRCUIT_OPEN: "熔断器打开",
            SystemErrorCategory.SERVER: "服务器错误",
            SystemErrorCategory.UNKNOWN: "未知错误",
            SystemErrorCategory.EMPTY_RESPONSE: "空响应",
            SystemErrorCategory.IDLE_TIMEOUT: "空闲超时",
        }
        return mapping.get(self, "未知错误")


# HTTP状态码到错误类型的映射
HTTP_STATUS_TO_ERROR_TYPE: Dict[int, SystemErrorCategory] = {
    400: SystemErrorCategory.SERVER,
    401: SystemErrorCategory.SERVER,
    403: SystemErrorCategory.SERVER,
    HTTP_RATE_LIMIT: SystemErrorCategory.SERVER,
    500: SystemErrorCategory.SERVER,
    502: SystemErrorCategory.SERVER,
    503: SystemErrorCategory.SERVER,
    504: SystemErrorCategory.SERVER,
}

# 错误类型到用户友好消息的映射
SYSTEM_ERROR_TYPE_TO_MESSAGE: Dict[SystemErrorCategory, Tuple[str, str]] = {
    SystemErrorCategory.CIRCUIT_OPEN: ("circuit_open", "服务暂时不可用,请稍后重试"),
    SystemErrorCategory.SERVER: ("server", "服务器错误,请稍后重试或更换模型"),
    SystemErrorCategory.UNKNOWN: ("unknown", "AI 处理异常,请稍后重试"),
    SystemErrorCategory.EMPTY_RESPONSE: ("empty_response", "AI服务返回空响应,请稍后重试"),
    SystemErrorCategory.IDLE_TIMEOUT: ("idle_timeout", "请求超时:AI模型30秒内未返回任何内容,已重试3次,请更换问题或稍后重试"),
}


class SystemErrorClassifier:
    """系统级错误分类器"""
    
    @staticmethod
    def _check_special_errors(error: Exception) -> Optional[SystemErrorCategory]:
        """检查特殊错误 — 白名单例外，走非SERVER路径 — 小沈 2026-07-05 移除EndOfStream(黑名单默认处理)"""
        if IdleTimeoutError and isinstance(error, IdleTimeoutError):
            return SystemErrorCategory.IDLE_TIMEOUT
        if FCFormatError and isinstance(error, FCFormatError):
            return SystemErrorCategory.UNKNOWN  # FC格式错误，重试无意义
        # EndOfStream 由黑名单默认SERVER处理，不需特殊case — 小沈 2026-07-05
        return None
    
    @staticmethod
    def _check_http_status_errors(error_msg: str) -> Optional[SystemErrorCategory]:
        """检查HTTP状态码错误"""
        for status_code, error_category in HTTP_STATUS_TO_ERROR_TYPE.items():
            if re.search(rf'\b{status_code}\b', error_msg):
                return error_category
        return None
    
    @staticmethod
    def classify_error(error: Exception) -> SystemErrorCategory:
        """
        分类系统级异常类型 — 黑名单策略，默认SERVER(retryable) — 小沈 2026-07-05
        
        黑名单原则：在LLM调用上下文中，绝大多数异常是网络/服务器问题，应重试。
        只有明确不该重试的（FC格式错、空响应、熔断、Python内置异常）才返回非SERVER。
        相比白名单（逐类列举httpx→httpcore→anyio异常，必然遗漏），
        黑名单不会漏掉httpx/httpcore/anyio任何层级的异常类型。
        
        Args:
            error: 异常对象
            
        Returns:
            SystemErrorCategory枚举值
        """
        error_msg = str(error).lower()
        
        # 1. 特殊错误（白名单例外，先于默认规则检查）
        category = SystemErrorClassifier._check_special_errors(error)
        if category:
            return category
        
        # 2. HTTP状态码错误 → SERVER(retryable)
        category = SystemErrorClassifier._check_http_status_errors(error_msg)
        if category:
            return category
        
        # 3. 系统级关键词
        if "circuit" in error_msg and "open" in error_msg:
            return SystemErrorCategory.CIRCUIT_OPEN
        
        if "empty" in error_msg and "response" in error_msg:
            return SystemErrorCategory.EMPTY_RESPONSE
        
        # 4. Python内置异常 → UNKNOWN（代码bug，重试无意义）— 小沈 2026-07-05
        _builtin_errors = {
            "ValueError", "TypeError", "AttributeError", "KeyError", "IndexError",
            "NameError", "SyntaxError", "RuntimeError",
        }
        if type(error).__name__ in _builtin_errors:
            return SystemErrorCategory.UNKNOWN
        
        # 5. 默认：SERVER(retryable) — 黑名单兜底
        #      httpx/httpcore/anyio 所有未识别异常类型自动走重试
        return SystemErrorCategory.SERVER
    
    @staticmethod
    def classify_error_message(error_type: str, error_message: str = "") -> Tuple[str, str]:
        """
        根据错误类型字符串分类,获取用户友好的错误信息
        
        Args:
            error_type: 错误类型标识
            error_message: 原始错误信息
            
        Returns:
            (code, message) 元组
        """
        error_type_lower = error_type.lower()
        for category in SystemErrorCategory:
            if category.value == error_type_lower or category.name.lower() == error_type_lower:
                if category in SYSTEM_ERROR_TYPE_TO_MESSAGE:
                    code, default_message = SYSTEM_ERROR_TYPE_TO_MESSAGE[category]
                    return code, default_message
        
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
        category = SystemErrorClassifier.classify_error(error)
        code, message = SystemErrorClassifier.classify_error_message(category.value, str(error))
        
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