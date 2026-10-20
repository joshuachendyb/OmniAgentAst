# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - A1工具层上下文(A2-越层延伸): _current_task_id ContextVar 从 services/task/task_context 下沉至 tools 层,
#   消除 tools→app.services.task 越层依赖(守护测试 tools 禁 app.services 规则); services/task/task_context 改为此处的薄壳
# 2026-08-12 - 小欧 - A1后半面(4.1.7 定案): 新增 _current_hooks ContextVar(get/set/reset), 承载入口层注入的安全 hooks。
#   默认值 None, 不预置 safety 实现(避免 tools→safety 违规), 由 tool_executor/health.py 两入口显式注入。
# 2026-08-13 - 小欧 - A1 类型对齐(三堂会审: 合规无环/合理类型增强/关联零行为变化): _current_hooks 标注 object→ToolSecurityHooks,
#   与设计 4.1.7 硬伤一保持一致(Protocol 仅 import typing, 同 tools 层无越层); 默认值仍 None, tool_executor getattr or 兜底不变。
# 2026-08-13 - 小沈 - 修复(三堂会审): 新增 get_current_hooks_or_noop() 兜底返回 NoOpHooks(非 None),
#   供工具内直接调用 .record_operation()/.execute_with_safety() 消除 NPE(入口未注入场景, 如测试直接调工具函数);
#   NoOpHooks 在 tools 层自给自足, 不破坏 A1 越层隔离。6 个文件工具改用本函数。
# 2026-10-20 - 北京老陈裁定(分层) - 会话工作区快照组迁至 app/session_workspace.py(四方共用, 置中立层解 safety→tools 越层); 本模块收窄为任务ID+安全钩子, 删 _current_ws 及相关旧历史(随代码迁走)。
# 2026-10-20 15:45 小欧 - 新增 _current_text_task ContextVar(get/set/reset): 承载入口层注入的"纯文本任务LLM调用回调"
#   (同压缩摘要 call_llm_text_task 一源的封装闭包)。工具层守护禁 tools→app.services, 故不像 hooks 一样预置实现,
#   而由 tool_executor 持 agent 在入口注入; 工具(如 fetchpage prompt提取)经 get_current_text_task 消费,
#   未注入时返回 None 由工具自行降级(零越层、零预设) — 小欧-2026-10-20
"""
tools/context — 工具层运行上下文

职责: 承载工具执行期间的请求作用域上下文(ContextVar), 供工具/日志等读取
会话工作区快照组已迁至 app/session_workspace.py(四方共用, 置中立层解 safety→tools 越层)
小欧 2026-08-12 A1下沉
"""
from contextvars import ContextVar
from typing import Optional

from app.tools.security_hooks import ToolSecurityHooks, NoOpHooks  # 修复: NoOpHooks 兜底 — 小沈 2026-08-13

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
_current_hooks: ContextVar[Optional[ToolSecurityHooks]] = ContextVar("current_hooks", default=None)
# "纯文本任务LLM调用回调": 入口层(tool_executor)持 agent 注入, 签名 async (messages: List[Dict]) -> str — 小欧 2026-10-20
_current_text_task: ContextVar[Optional[object]] = ContextVar("current_text_task", default=None)

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
    """获取当前作用域 hooks, 未注入时返回 NoOpHooks 兜底(非 None) — 小沈 2026-08-13 修复

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


def get_current_text_task() -> Optional[object]:
    """获取当前作用域的纯文本任务LLM调用回调(入口层注入) — 小欧 2026-10-20
    返回 None 表示未注入(直接调工具/无agent场景), 由工具自行降级。
    """
    return _current_text_task.get()


def set_current_text_task(callable_text_task):
    """设置当前作用域的纯文本任务LLM调用回调, 返回 token 供 reset — 小欧 2026-10-20"""
    return _current_text_task.set(callable_text_task)


def reset_current_text_task(token) -> None:
    """恢复上一个纯文本任务回调 — 小欧 2026-10-20"""
    _current_text_task.reset(token)
