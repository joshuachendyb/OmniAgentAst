# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-17 - 小欧 - 新增 session_id_var(ContextVar): 承载请求作用域的会话标识, 供日志 Filter 注入实现多会话日志隔离; 复用本模块已有的 ContextVar 模式, 不新建独立模块
# 2026-07-30 - 小沈 - 迁出 session_id_var 至 logger.shared_handler（SRP: task_context 只应管 taskId）; 扩展 get/set/reset_current_task_id 三个函数
# 2026-08-12 - 小欧 - A1下沉: 任务ID ContextVar 本体迁至 app.tools.context, 本模块降为薄壳 re-export,
#   消除 tools 层对 app.services.task 的越层依赖(守护测试 tools 禁 app.services 规则)
# 2026-08-12 - 小欧 - 补 _current_task_id re-export: health.py/openai.py 仍从本薄壳导入, 保持可用 — 小欧 2026-08-12
"""
task_context — 任务ID ContextVar（从 utils/message_id_tracker.py 拆分）
小欧 2026-07-10
A1下沉后为薄壳: 实际实现见 app.tools.context — 小欧 2026-08-12
"""

from app.tools.context import (  # noqa: F401 — 薄壳 re-export, tools 层直接引用 app.tools.context
    get_current_task_id,
    reset_current_task_id,
    set_current_task_id,
    _current_task_id,
)
