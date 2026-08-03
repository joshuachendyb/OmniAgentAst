# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-17 - 小欧 - 新增 session_id_var(ContextVar): 承载请求作用域的会话标识, 供日志 Filter 注入实现多会话日志隔离; 复用本模块已有的 ContextVar 模式, 不新建独立模块
# 2026-07-30 - 小沈 - 迁出 session_id_var 至 logger.shared_handler（SRP: task_context 只应管 taskId）; 扩展 get/set/reset_current_task_id 三个函数
"""
task_context — 任务ID ContextVar（从 utils/message_id_tracker.py 拆分）
小欧 2026-07-10
"""

from contextvars import ContextVar
from typing import Optional

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)


def get_current_task_id() -> Optional[str]:
    """获取当前任务的 taskId — 小沈 2026-07-30"""
    return _current_task_id.get()


def set_current_task_id(task_id: str):
    """设置当前任务的 taskId — 小沈 2026-07-30"""
    _current_task_id.set(task_id)


def reset_current_task_id():
    """重置当前任务的 taskId — 小沈 2026-07-30"""
    _current_task_id.set(None)
