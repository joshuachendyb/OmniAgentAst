# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-10 - 小欧 - 会话使用的目录 任务级快照: 新增 _current_ws ContextVar + WorkspaceSnapshot。
#   all_paths 在 build 时一次算好, 读路径零遍历。元素类型是 str(消费侧三处宿主
#   类型各不相同, 并入前必须各自转 Path, 见各消费点注释)。
# 2026-10-10 - 小欧 - 概念订正: 删 is_default / manual_paths —— 本快照只装"会话使用的目录",
#   表里没有"授权目录"可供区分(授权归全局 config), 故无需分档。
# 2026-10-15 北京老陈裁定(分层) - 自 app/tools/context.py 迁入: 本组被 safety(3处)/tools(1处)/services(1处) 四方共用, 寄居 tools 层使 safety 必然越层; app 根是本项目既有中立层(config/constants 六层全 import), 迁此四方依赖方向全合法。业务逻辑逐字搬迁不改。
"""
session_workspace — 会话工作区任务级快照

四方共用, 故置于中立层 app 根:
  services/chat/stream_orchestrator  构造并注入
  safety/path_env、path_classify_category、delete_safety  读作受保护根来源
  ★2026-10-16: 原第2行 tools/file/delete_file(读作删除硬底线范围) 已随该硬底线删除而失效 ——
    delete_file 不再 import 本模块, 现为三方共用。

BUG-18(潜伏,非缺陷): 载体是 ContextVar, 靠 asyncio.create_task / asyncio.to_thread 自动传播,
ThreadPoolExecutor 不传(实测)。全仓工具执行只走上述两条, 当前无暴露面。
"""
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WorkspaceEntry:
    """单条会话使用的目录。frozen: 快照只读, 消费方只读不写"""
    path: str


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """任务级快照。两种形态在构造时一次算完, 读路径零遍历零过滤

    all_paths — 整个会话目录列表, 并入写/删白名单(path_env / delete_safety)
                ★2026-10-16: 原"并作为删除根硬拦(delete_file)"已随该硬底线删除而失效

    BUG-18 说明(潜伏,非缺陷): 载体是 ContextVar, 靠 asyncio.create_task /
    asyncio.to_thread 自动传播, ThreadPoolExecutor 不传(实测)。
    全仓工具执行只走上述两条(fetch_webpage 的裸池只做页面渲染不碰路径校验),
    故当前无暴露面。后来者若用裸池跑"写文件"类工具, 必须显式传快照, 不得隐式依赖。
    """
    entries: tuple[WorkspaceEntry, ...]
    all_paths: frozenset

    @classmethod
    def build(cls, entries) -> "WorkspaceSnapshot":
        entries = tuple(entries)
        return cls(entries=entries, all_paths=frozenset(_drop_nested(e.path for e in entries)))


def _drop_nested(paths) -> list:
    """去掉被同组其它路径包含的子路径（BUG-16）

    前缀匹配下子项恒冗余: `C:\a` 在白名单里时 `C:\a\b` 不改变任何裁决,
    只会让白名单越堆越长。只留顶层, 裁决结果不变。
    比较大小写不敏感（Windows）, 分隔符兼受 `/` 与 `\`。
    面板读库直显不受影响（面板不走快照）。"""
    tops: list[str] = []
    for p in sorted(set(paths), key=len):     # 短的在前, 先占顶
        _lp = p.lower().replace("/", "\\")
        if any(_lp == t or _lp.startswith(t + "\\")
               for t in (q.lower().replace("/", "\\") for q in tops)):
            continue
        tops.append(p)
    return tops


_current_ws: ContextVar[Optional[WorkspaceSnapshot]] = ContextVar("tool_session_ws", default=None)


def set_current_session_workspaces(snapshot: WorkspaceSnapshot):
    """设置本任务快照; 返回 token 供 reset(与 set_current_hooks 同款形态)"""
    return _current_ws.set(snapshot)


def get_ws_snapshot() -> Optional[WorkspaceSnapshot]:
    """取本任务快照; 未注入返 None(单测直接调工具时的正常态)"""
    return _current_ws.get()


def session_workspace_paths() -> list:
    """本会话工作区目录列表(安全判定的受保护根来源之一)"""
    snap = get_ws_snapshot()
    return list(snap.all_paths) if snap else []


def reset_current_session_workspaces(token) -> None:
    """恢复上一个快照; 必须用 set 返回的 token, 直接 set 会抛错不静默"""
    _current_ws.reset(token)


__all__ = ["WorkspaceEntry", "WorkspaceSnapshot", "get_ws_snapshot",
           "set_current_session_workspaces", "reset_current_session_workspaces",
           "session_workspace_paths"]