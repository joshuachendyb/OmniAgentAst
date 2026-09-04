# -*- coding: utf-8 -*-
# 编辑历史: 2026-09-03 小欧 - 新建: 冲突检测三函数下沉，解耦 action_handler - 小欧-2026-09-03
# 编辑历史: 2026-09-04 小健 - 修正: 复用 trust._parse_paths，禁止重写简化退化 - 小健-2026-09-04
# 编辑历史: 2026-09-04 小健 - 修正: trust_utils已合并为trust.py，import路径同步更新 - 小健-2026-09-04
# 编辑历史: 2026-09-04 小健 - 修正: 从action_handler.py精确复制完整版_has_conflict/_partition_calls,
#   补全窗口工具支持(WINDOW_TARGET_TOOLS)/计数版冲突判定(count>=2)/索引返回(List[List[int]]) - 小健-2026-09-04
"""冲突检测: 路径/窗口冲突判定与调用分组（精确复制自action_handler.py:552-616）

职责: 纯函数，无副作用
- _has_conflict: 检测路径/窗口冲突（计数版，支持窗口工具）
- _partition_calls: 按路径/窗口相关性分组（并查集，返回索引列表）
"""
from typing import Any, Dict, List
from app.tools.trust import _parse_paths, WINDOW_TARGET_TOOLS
from app.tools.tool_constants import FILE_OPERATION_TOOLS
from app.logger import logger

# 写操作工具集: FILE_OPERATION_TOOLS - 只读工具（精确复制自 action_handler.py:230-232）
_READ_TOOLS = {"readtext", "read_xlsx", "read_docx", "read_pdf", "read_pptx"}
_WRITE_OPS = FILE_OPERATION_TOOLS - _READ_TOOLS


def _has_conflict(all_calls: List[Dict]) -> bool:
    """检测路径/窗口冲突 — 北京老陈 2026-07-04 初版; 小欧 2026-08-09 计数版; 小欧 2026-08-11 窗口工具纳入
    冲突：同一键(文件路径/窗口标题)被>=2次调用访问, 且(至少一个文件写操作 或 含窗口工具)
    有冲突→顺序执行, 无冲突→并行
    [2026-08-09 小欧] BUG修复: 旧实现用 set 存工具名不计数, 同名工具多次写
    同一路径漏检(3×edittext 同文件)→误走并行→read-modify-write 竞态致内容丢失。
    改为 path→(调用次数, 工具名set), 复用 _parse_paths 解析(与 _partition_calls 一致, DRY)。
    [2026-08-11 小欧] 扩展: 窗口工具(window_focus/window_resize/set_window_state)同标题即冲突,
    消除 task002 实测 P2(restore+resize 同批并行→resize 0.00s 莫名失败)的并行竞态。
    注: 文件路径键与 "window:" 键空间不重叠, 同一 entry 的 tools 不会混合文件与窗口工具。
    精确复制自 action_handler.py:552-582 — 小健-2026-09-04
    """
    path_ops: Dict[str, Dict[str, Any]] = {}

    def _record(_path: str, _name: str) -> None:
        entry = path_ops.setdefault(_path, {"count": 0, "tools": set()})
        entry["count"] += 1
        entry["tools"].add(_name)

    for c in all_calls:
        name = c.get("tool_name", "")
        if name not in FILE_OPERATION_TOOLS and name not in WINDOW_TARGET_TOOLS:
            continue
        for _path in _parse_paths(name, c.get("tool_params", {})):
            _record(_path, name)

    for path, entry in path_ops.items():
        tools = entry["tools"]
        if entry["count"] >= 2 and (any(t in _WRITE_OPS for t in tools) or any(t in WINDOW_TARGET_TOOLS for t in tools)):
            logger.info(f"[_has_conflict] 操作冲突(路径/窗口): {path}, tools={tools}, 调用数={entry['count']}, 降级顺序执行")
            return True
    return False


def _partition_calls(all_calls: List[Dict]) -> List[List[int]]:
    """按路径/窗口相关性分组(并查集连通分量): 共享路径或同标题窗口的调用归一组, 组间无共享→可并行
    返回: 组列表, 每组是 all_calls 的索引列表 — 小欧 2026-08-09 — 小欧 2026-08-11 窗口工具自动纳入
    (窗口工具经 _parse_paths 返回 "window:标题" 冲突键, 同标题自动并组串行, 分组本体逻辑零改动)
    精确复制自 action_handler.py:585-616 — 小健-2026-09-04
    """
    n = len(all_calls)
    parent = list(range(n))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    path_to_calls = {}
    for i, c in enumerate(all_calls):
        for p in _parse_paths(c.get("tool_name", ""), c.get("tool_params", {})):
            path_to_calls.setdefault(p, []).append(i)
    for _p, idxs in path_to_calls.items():
        base = idxs[0]
        for i in idxs[1:]:
            _union(base, i)

    groups = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)
    return list(groups.values())
