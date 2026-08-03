# -*- coding: utf-8 -*-
"""
task_context — 任务ID ContextVar

从 utils/message_id_tracker.py 拆分
小欧 2026-07-10
# 编辑历史:
# 2026-07-17 - 小欧 - 新增 session_id_var(ContextVar): 承载请求作用域的会话标识, 供日志 Filter 注入实现多会话日志隔离; 复用本模块已有的 ContextVar 模式, 不新建独立模块
"""

from contextvars import ContextVar
from typing import Optional

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
# session_id 载体: 在 chat 请求入口 set, 日志 Filter 读取注入 record, 默认值为 '-'(无会话上下文时) — 小欧 2026-07-17
session_id_var: ContextVar[str] = ContextVar("session_id", default="-")
