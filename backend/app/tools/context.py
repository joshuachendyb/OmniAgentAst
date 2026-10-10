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
# 2026-10-10 - 小欧 - 会话使用的目录 任务级快照: 新增 _current_ws ContextVar + WorkspaceSnapshot。
#   all_paths 在 build 时一次算好, 读路径零遍历。元素类型是 str(消费侧三处宿主
#   类型各不相同, 并入前必须各自转 Path, 见各消费点注释)。
# 2026-10-10 - 小欧 - 概念订正: 删 is_default / manual_paths —— 本快照只装"会话使用的目录",
#   表里没有"授权目录"可供区分(授权归全局 config), 故无需分档。
"""
tools/context — 工具层运行上下文

职责: 承载工具执行期间的请求作用域上下文(ContextVar), 供工具/日志等读取
依赖方向: tools 层自给自足, 不再依赖 services 层
小欧 2026-08-12 A1下沉
"""
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from app.tools.security_hooks import ToolSecurityHooks, NoOpHooks  # 修复: NoOpHooks 兜底 — 小沈 2026-08-13

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
_current_hooks: ContextVar[Optional[ToolSecurityHooks]] = ContextVar("current_hooks", default=None)
_current_ws: ContextVar[Optional["WorkspaceSnapshot"]] = ContextVar("tool_session_ws", default=None)


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


# ===== 会话 Workspace 任务级快照 ————————————————————————————————
@dataclass(frozen=True)
class WorkspaceEntry:
    """单条会话使用的目录。frozen: 快照只读, 消费方只读不写"""
    path: str


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """任务级快照。两种形态在构造时一次算好, 读路径零遍历零过滤。

    all_paths — 整个会话目录列表, 并入写白名单(path_safe_check / delete_safety)
              并作为删除根硬拦(delete_file)

    BUG-18 说明（潜伏，非缺陷）：载体是 ContextVar，靠 `asyncio.create_task` /
    `asyncio.to_thread` 自动传播；**裸 ThreadPoolExecutor 不传播**（实测）。
    全仓工具执行只走上述两条（fetch_webpage 的裸池只做页面渲染不碰路径校验），
    故当前无暴露面。后来者若用裸池跑"写文件"类工具，必须显式传快照，不得隐式依赖。
    """
    entries: tuple[WorkspaceEntry, ...]
    all_paths: frozenset

    @classmethod
    def build(cls, entries) -> "WorkspaceSnapshot":
        entries = tuple(entries)
        return cls(entries=entries, all_paths=frozenset(_drop_nested(e.path for e in entries)))


def _drop_nested(paths) -> list:
    """去掉被同组其它路径包含的子路径（BUG-16）。

    前缀匹配下子项恒冗余：`C:\\a` 在白名单里时 `C:\\a\\b` 不改变任何裁决，
    只会让白名单越堆越长。只留顶层，裁决结果不变。
    比较大小写不敏感（Windows），分隔符兼容 `/` 与 `\\`。
    面板读库直显不受影响（面板不走快照）。"""
    tops: list[str] = []
    for p in sorted(set(paths), key=len):     # 短的在前，先占顶层
        _lp = p.lower().replace("/", "\\")
        if any(_lp == t or _lp.startswith(t + "\\")
               for t in (q.lower().replace("/", "\\") for q in tops)):
            continue
        tops.append(p)
    return tops


def set_current_session_workspaces(snapshot: WorkspaceSnapshot):
    """设置本任务快照, 返回 token 供 reset — 与 set_current_hooks 同款形态"""
    return _current_ws.set(snapshot)


def get_ws_snapshot() -> Optional[WorkspaceSnapshot]:
    """取本任务快照; 未注入返回 None(单测直接调工具时的正常态)"""
    return _current_ws.get()


def reset_current_session_workspaces(token) -> None:
    """恢复上一个快照 — 必须传 set 返回的 token, 错 token 会直接抛错不静默"""
    _current_ws.reset(token)
