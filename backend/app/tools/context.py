# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - A1工具层上下文(A2-越层延伸): _current_task_id ContextVar 从 services/task/task_context 下沉至 tools 层,
#   消除 tools→app.services.task 越层依赖(守护测试 tools 禁 app.services 规则); services/task/task_context 改为此处的薄壳
# 2026-08-12 - 小欧 - A1后半面(4.1.7 定案): 新增 _current_hooks ContextVar(get/set/reset), 承载入口层注入的安全 hooks。
#   默认值 None, 不预置 safety 实现(避免 tools→safety 违规), 由 tool_executor/health.py 两入口显式注入。
# 2026-08-13 - 小欧 - A1 类型对齐(三堂会审: 合规无环/合理类型增强/关联零行为变化): _current_hooks 标注 object→ToolSecurityHooks,
#   与设计 4.1.7 硬伤一保持一致(Protocol 仅 import typing, 同 tools 层无越层); 默认值仍 None, tool_executor getattr or 兜底不变。
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): 新增 get_current_hooks_or_noop() 兜底返回 NoOpHooks(非 None),
#   供工具内直接调用 .record_operation()/.execute_with_safety() 消除 NPE(入口未注入场景, 如测试直接调工具函数);
#   NoOpHooks 在 tools 层自给自足, 不破坏 A1 越层隔离。6 个文件工具改用本函数。
"""
tools/context — 工具层运行上下文

职责: 承载工具执行期间的请求作用域上下文(ContextVar), 供工具/日志等读取
依赖方向: tools 层自给自足, 不再依赖 services 层
小欧 2026-08-12 A1下沉
"""
from contextvars import ContextVar
from typing import Optional

from app.tools.security_hooks import ToolSecurityHooks, NoOpHooks  # BUG-3修复: NoOpHooks 兜底 — 小沈 2026-08-13

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
_current_hooks: ContextVar[Optional[ToolSecurityHooks]] = ContextVar("current_hooks", default=None)


def get_current_task_id() -> Optional[str]:
    """获取当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    return _current_task_id.get()


def set_current_task_id(task_id: str):
    """设置当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    _current_task_id.set(task_id)


def reset_current_task_id():
    """重置当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    _current_task_id.set(None)


def get_current_hooks() -> Optional[ToolSecurityHooks]:
    """获取当前作用域的安全 hooks(入口层注入) — 小欧 2026-08-12
    返回 None 表示入口未注入(正常流程下 tool_executor/health.py 均已注入)。
    """
    return _current_hooks.get()


def get_current_hooks_or_noop() -> ToolSecurityHooks:
    """获取当前作用域 hooks, 未注入时返回 NoOpHooks 兜底(非 None) — 小沈 2026-08-13 BUG-3修复

    供工具内直接调用 .record_operation()/.execute_with_safety() 使用,
    消除 `None.record_operation()` NPE(入口未注入场景, 如测试直接调工具函数)。
    NoOpHooks 不依赖 safety 层, tools 自给自足, 不破坏 A1 越层隔离。
    """
    return _current_hooks.get() or NoOpHooks()


def set_current_hooks(hooks: ToolSecurityHooks):
    """设置当前作用域 hooks, 返回 token 供 reset — 小欧 2026-08-12"""
    return _current_hooks.set(hooks)


def reset_current_hooks(token) -> None:
    """恢复上一个 hooks — 小欧 2026-08-12"""
    _current_hooks.reset(token)
