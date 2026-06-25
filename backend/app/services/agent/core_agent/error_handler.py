# -*- coding: utf-8 -*-
"""
error_handler — 统一ReAct循环错误处理 — 小欧 2026-06-25

设计: 模块级函数, 不用类。if/elif直接分派, 不用注册表(KISS-DIRECT)。
与exit_with_error的关系: error_handler是exit_with_error的替代(仅限react_cycle循环异常处)。
exit_with_error保留不动, 用于确定要FAILED的场景(空响应/安全blocked/用户拒绝)。
"""

from app.services.agent.steps import ErrorStep
from app.services.agent.types import AgentStatus
from app.utils.logger import logger


def handle_react_error(agent, error, step):
    """统一处理ReAct循环中的错误 — if/elif直接分派 — 小欧 2026-06-25"""
    error_type = _classify_error(error)

    if error_type == "fc_format_error":
        return _handle_fc_format_error(agent, error, step)
    elif error_type == "network_error":
        return _handle_network_error(agent, error, step)
    else:
        agent.set_failed(str(error))
        return ErrorStep(step=step, error_type="unknown_error", error_message=str(error))


def _classify_error(error):
    """错误分类 — 基于异常类型, 不基于字符串匹配 — 小欧 2026-06-25"""
    from app.services.llm.core import FCFormatError
    from app.utils.error_classifier import UnifiedErrorClassifier, ErrorCategory

    if isinstance(error, FCFormatError):
        return "fc_format_error"

    category = UnifiedErrorClassifier.classify_error(error)
    if category in (ErrorCategory.NETWORK, ErrorCategory.CONNECT, ErrorCategory.TIMEOUT, ErrorCategory.EMPTY_RESPONSE):
        return "network_error"

    return "unknown_error"


def _handle_fc_format_error(agent, error, step):
    """FC格式错误 → 可重试 — 小欧 2026-06-25"""
    logger.error(f"[ErrorHandler] FC格式错误: {error}")
    agent.status = AgentStatus.RETRYABLE_ERROR
    return ErrorStep(step=step, error_type="fc_format_error",
                     error_message=str(error), recoverable=True)


def _handle_network_error(agent, error, step):
    """网络错误 → 可重试 — 小欧 2026-06-25"""
    logger.error(f"[ErrorHandler] 网络错误: {error}")
    agent.status = AgentStatus.RETRYABLE_ERROR
    return ErrorStep(step=step, error_type="network_error",
                     error_message=str(error), recoverable=True)