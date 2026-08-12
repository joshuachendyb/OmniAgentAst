# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - A1工具层上下文(A2-越层延伸): _current_task_id ContextVar 从 services/task/task_context 下沉至 tools 层,
#   消除 tools→app.services.task 越层依赖(守护测试 tools 禁 app.services 规则); services/task/task_context 改为此处的薄壳
# 2026-08-12 - 小欧 - A1后半面(4.1.7 定案): 新增 _current_hooks ContextVar(get/set/reset), 承载入口层注入的安全 hooks。
#   默认值 None, 不预置 safety 实现(避免 tools→safety 违规), 由 tool_executor/health.py 两入口显式注入。
"""
tools/context — 工具层运行上下文

职责: 承载工具执行期间的请求作用域上下文(ContextVar), 供工具/日志等读取
依赖方向: tools 层自给自足, 不再依赖 services 层
小欧 2026-08-12 A1下沉
"""
from contextvars import ContextVar
from typing import Optional

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
_current_hooks: ContextVar[Optional[object]] = ContextVar("current_hooks", default=None)


def get_current_task_id() -> Optional[str]:
    """获取当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    return _current_task_id.get()


def set_current_task_id(task_id: str):
    """设置当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    _current_task_id.set(task_id)


def reset_current_task_id():
    """重置当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    _current_task_id.set(None)


def get_current_hooks() -> Optional[object]:
    """获取当前作用域的安全 hooks(入口层注入) — 小欧 2026-08-12
    返回 None 表示入口未注入(正常流程下 tool_executor/health.py 均已注入)。
    """
    return _current_hooks.get()


def set_current_hooks(hooks: object):
    """设置当前作用域 hooks, 返回 token 供 reset — 小欧 2026-08-12"""
    return _current_hooks.set(hooks)


def reset_current_hooks(token) -> None:
    """恢复上一个 hooks — 小欧 2026-08-12"""
    _current_hooks.reset(token)
