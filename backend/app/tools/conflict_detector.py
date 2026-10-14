# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: 冲突检测下沉, 解耦 action_handler - 小健-2026-09-04
# 2026-10-02 - 小欧 - 注册名归位: _READ_TOOLS 文本项 read→read, 与 FUNDAMENTAL 侧 read 别名删除同步
# 2026-10-14 - 小欧 - 文档[33] 4.11-B/4.11-C: 接收 trust 迁入的 _parse_paths(冲突键解析唯一消费方在此, 原挂 trust 属 SRP 债); WINDOW_TARGET_TOOLS 改从 tool_constants 导入
"""
conflict_detector — 工具调用冲突检测: 路径/窗口冲突判定 + 并查集分组

从 action_handler.py 提取:
- _has_conflict: 检测同批调用是否存在文件路径/窗口冲突（计数版）
- _partition_calls: 并查集连通分量分组（冲突组内串行，无冲突组并行）

原则: 完整复制, 保留原始功能分支和逻辑, 禁止简化退化
"""
from typing import Dict, List, Any, Set
# 2026-10-14 小欧 - 文档[33] 4.11-B/4.11-C: WINDOW_TARGET_TOOLS 归 tool_constants,
#   _parse_paths 由 trust 迁入本文件(唯一消费方在此, 原挂 trust 属 SRP 债)。
from app.tools.tool_constants import FILE_OPERATION_TOOLS, WINDOW_TARGET_TOOLS
from app.tools.tools_alias_mapper import PARAM_ALIASES
from app.logger import logger

# 工具文件读操作集合（冲突检测用）— 小欧 2026-08-13
# 同路径多次调用判定: 读-读无竞态不冲突(仍并行), 仅需从写集合排除, 防 read_xlsx 等被误判写操作致并行退化串行
# 2026-09-24 北京老陈 方案1: 加"read"(fundamental别名工具, 与read同参与冲突检测)
_READ_TOOLS = {"read", "read_xlsx", "read_docx", "read_pdf", "read_pptx"}
# 工具文件写操作集合（冲突检测用）— 北京老陈 2026-07-04
_WRITE_OPS = FILE_OPERATION_TOOLS - _READ_TOOLS


# ════════════════════════════════════════════════════════════
# 冲突键解析（迁自 app/tools/trust.py:38 — 文档[33] 4.11-C）
# ════════════════════════════════════════════════════════════

def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径/窗口冲突键集合(复用 PARAM_ALIASES 别名→规范名) — 小欧 2026-08-09 — 小欧 2026-08-11 窗口分支
    文件工具: 解析 path 集合(与 _has_conflict/_partition_calls 共用, DRY)。
    窗口工具: 以 "window:{window_title}" 为冲突键, 同标题窗口工具并入同组串行(状态变更非幂等);
              缺 window_title 返回空集——窗口工具参数校验必失败, 不会操作任何窗口, 无竞态风险, 不参与分组。
    完整复制自 action_handler.py:551-578，保留别名映射逻辑，禁止简化退化

    迁自 `app/tools/trust.py:38`（文档[33] 4.11-C）—— 落点判据: 唯一消费方是本模块的
    _has_conflict / _partition_calls, 挂 trust 属 SRP 债, 且致 conflict_detector 反向 import trust。
    """
    if name in WINDOW_TARGET_TOOLS:
        title = params.get("window_title", "")
        if title and isinstance(title, str):
            return {f"window:{title}"}
        return set()
    if name not in FILE_OPERATION_TOOLS:
        return set()
    aliases = PARAM_ALIASES.get(name, {})
    if not aliases:
        p = params.get("path", "")
        return {p} if p and isinstance(p, str) else set()
    resolved = {}
    for key, value in params.items():
        canon = aliases.get(key, key)
        if canon not in resolved:
            resolved[canon] = value
    out = set()
    for pname in set(aliases.values()):
        pval = resolved.get(pname)
        if pval and isinstance(pval, str):
            out.add(pval)
    return out


# ════════════════════════════════════════════════════════════
# 冲突检测（复制自 action_handler.py:590-621）
# ════════════════════════════════════════════════════════════

def _has_conflict(all_calls: List[Dict]) -> bool:
    """检测路径/窗口冲突 — 北京老陈 2026-07-04 初版; 小欧 2026-08-09 计数版; 小欧 2026-08-11 窗口工具纳入
    冲突：同一键(文件路径/窗口标题)被>=2次调用访问, 且(至少一个文件写操作 或 含窗口工具)
    有冲突→顺序执行, 无冲突→并行
    完整复制自 action_handler.py:590-621
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


# ════════════════════════════════════════════════════════════
# 并查集分组（复制自 action_handler.py:623-655）
# ════════════════════════════════════════════════════════════

def _partition_calls(all_calls: List[Dict]) -> List[List[int]]:
    """按路径/窗口相关性分组(并查集连通分量): 共享路径或同标题窗口的调用归一组, 组间无共享→可并行
    返回: 组列表, 每组是 all_calls 的索引列表 — 小欧 2026-08-09 — 小欧 2026-08-11 窗口工具自动纳入
    完整复制自 action_handler.py:623-655
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
