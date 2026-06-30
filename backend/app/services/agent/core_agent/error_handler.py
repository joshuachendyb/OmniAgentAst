# -*- coding: utf-8 -*-
"""
error_handler — 统一ReAct循环错误处理 — 小欧 2026-06-25

设计: 模块级函数, 不用类。if/elif直接分派, 不用注册表(KISS-DIRECT)。
与exit_with_error的关系: error_handler是exit_with_error的替代(仅限react_cycle循环异常处)。
exit_with_error保留不动, 用于确定要FAILED的场景(空响应/安全blocked/用户拒绝)。
"""

from app.services.agent.steps import ErrorStep
from app.utils.logger import logger


def handle_react_error(agent, error, step):
    """统一处理ReAct循环中的错误 — 均走 set_failed() — 小欧 2026-06-29"""
    from app.utils.sys_error_classifier import SystemErrorClassifier
    error_type = SystemErrorClassifier.classify_error(error).name.lower()
    logger.error(f"[ErrorHandler] 错误类型={error_type}: {error}")
    agent.set_failed(str(error))
    return ErrorStep(step=step, error_type=error_type, error_message=str(error))


