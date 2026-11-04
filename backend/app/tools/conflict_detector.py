# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: 冲突检测下沉, 解耦 action_handler - 小健-2026-09-04
# 2026-10-02 - 小欧 - 注册名归位: _READ_TOOLS 文本项 read→read, 与 FUNDAMENTAL 侧 read 别名删除同步
# 2026-10-14 - 小欧 - 接收 trust 迁入的 _parse_paths(冲突键解析唯一消费方在此, 原挂 trust 属 SRP 债); WINDOW_TARGET_TOOLS 改从 tool_constants 导入
# 2026-10-19 小欧 - 同库 SQL 调用纳入冲突键: 原冲突键仅认 FILE_OPERATION_TOOLS/WINDOW_TARGET_TOOLS,
#   execute_sql 的 path 被忽略 → 同批 CREATE+INSERT 落入不同组并行执行 → INSERT 抢在 CREATE 提交前读到
#   "no such table"; 新增 _conflict_keys(sqlite 取 path/远端库取 connection_string), execute_sql 计入写操作,
#   同库写+写/写+读并组串行, 不同库仍并行; _parse_paths 保持原样以免改变 trust 信任口径
# 2026-10-19 小欧 - 冲突检测改为"身份键 + 规范名":
#   ① 工具名取 _normal_name(解析层归一唯一真源), 别名(write_text/read_text)不再漏检;
#   ② 路径键做 abspath+normcase 归一, 相对/绝对、大小写变体视为同一文件;
#   ③ 远端库键经 make_url 取 backend/host/port/database(去账号口令), 同库不同连接串/不同口令不再漏并组;
#   _parse_paths 仍返回原值供 trust 使用, 归一化只在 _conflict_keys 内完成(不动信任口径)
"""
conflict_detector — 工具调用冲突检测: 路径/窗口冲突判定 + 并查集分组

从 action_handler.py 提取:
- _has_conflict: 检测同批调用是否存在文件路径/窗口/数据库冲突（计数版）
- _partition_calls: 并查集连通分量分组（冲突组内串行，无冲突组并行）
- _conflict_keys: 冲突键 = 路径/窗口键 + SQL 库键（同库写操作须串行）

原则: 完整复制, 保留原始功能分支和逻辑, 禁止简化退化
"""
import os
import hashlib
from typing import Dict, List, Any, Set
# 2026-10-14 小欧 - WINDOW_TARGET_TOOLS 归 tool_constants,
#   _parse_paths 由 trust 迁入本文件(唯一消费方在此, 原挂 trust 属 SRP 债)。
from app.tools.tool_constants import FILE_OPERATION_TOOLS, WINDOW_TARGET_TOOLS
from app.tools.tools_alias_mapper import PARAM_ALIASES
from app.logger import logger

# 工具文件读操作集合（冲突检测用）— 小欧 2026-08-13
# 同路径多次调用判定: 读-读无竞态不冲突(仍并行), 仅需从写集合排除, 防 read_xlsx 等被误判写操作致并行退化串行
# 2026-09-24 北京老陈 方案1: 加"read"(fundamental别名工具, 与read同参与冲突检测)
_READ_TOOLS = {"read", "read_xlsx", "read_docx", "read_pdf", "read_pptx"}
# SQL 工具: sqlite 以 path、远端库以 connection_string 作为冲突键 — 小欧 2026-10-19
_SQL_TOOLS = {"execute_sql", "query_sql", "get_db_schema"}
# SQL 写操作: 同库 DDL/DML 必须串行, 防未提交的表对同批其它连接不可见 — 小欧 2026-10-19
_SQL_WRITE_TOOLS = {"execute_sql"}
# 工具文件写操作集合（冲突检测用）— 北京老陈 2026-07-04
_WRITE_OPS = (FILE_OPERATION_TOOLS - _READ_TOOLS) | _SQL_WRITE_TOOLS


# ════════════════════════════════════════════════════════════
# 冲突键解析（迁自 app/tools/trust.py）
# ════════════════════════════════════════════════════════════

def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径/窗口冲突键集合(复用 PARAM_ALIASES 别名→规范名) — 小欧 2026-08-09 — 小欧 2026-08-11 窗口分支
    文件工具: 解析 path 集合(被 _conflict_keys 调用后供分组复用; 亦被 trust.extract_trust_path 复用)。
    窗口工具: 以 "window:{window_title}" 为冲突键, 同标题窗口工具并入同组串行(状态变更非幂等);
              缺 window_title 返回空集——窗口工具参数校验必失败, 不会操作任何窗口, 无竞态风险, 不参与分组。
    注意: 本函数同时被 trust.extract_trust_path 复用, 不承担 SQL 冲突键(见 _conflict_keys) — 小欧 2026-10-19
    完整复制自 action_handler.py，保留别名映射逻辑，禁止简化退化
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


def _tool_name_of(call: Dict) -> str:
    """取调用的规范工具名: 优先解析层归一的 _normal_name, 回落原始 tool_name — 小欧 2026-10-19
    别名(write_text/read_text 等)经 tools_alias_mapper 归一, 官方真源是 action_input_parser 写入的 _normal_name;
    冲突检测若读原始 tool_name 会把别名误当未知工具跳过, 致同文件写×2/读+写漏判并行。
    """
    return call.get("_normal_name") or call.get("tool_name", "")


def _canonical_path(p: str) -> str:
    """路径身份归一: abspath + normcase(Windows 不区分大小写), 相对/绝对/大小写变体视为同一文件 — 小欧 2026-10-19
    仅用于冲突判定, 不改变 _parse_paths 返回的原值(trust 口径不受影响)。
    window:/db: 前缀键与非字符串原样返回。
    """
    if not isinstance(p, str) or not p or p.startswith("window:") or p.startswith("db:"):
        return p
    try:
        return os.path.normcase(os.path.abspath(p))
    except (OSError, ValueError):
        return p


def _db_key(conn_str: str) -> str:
    """远端库身份键: 经 make_url 取 backend/host/port/database, 忽略账号与口令 — 小欧 2026-10-19
    同库不同口令/不同账号视为同一库(仍须并组串行); 解析失败回落连接串哈希(仍可区分不同库, 且不含明文可安全入日志)。
    """
    try:
        from sqlalchemy.engine.url import make_url
        u = make_url(conn_str)
        return f"db:{u.get_backend_name()}://{u.host or ''}:{u.port or ''}/{u.database or ''}"
    except Exception:
        return "db:" + hashlib.sha1(conn_str.encode("utf-8")).hexdigest()[:16]


def _conflict_keys(name: str, params: Dict) -> Set[str]:
    """冲突键 = 路径/窗口键(身份归一) + SQL 库键 — 小欧 2026-10-19
    数据库冲突键与 _parse_paths 分设: 后者被 trust.extract_trust_path 复用, 混入 connection_string
    会改变 HITL 信任落库/查询口径(远端库由工具级通配变按连接串), 属越界副作用。
    sqlite 用 path(与文件工具同路径归一后天然同组); 远端库用 "db:" 前缀 + 身份键防与文件路径混淆。
    """
    keys = {_canonical_path(k) for k in _parse_paths(name, params or {})}
    if name not in _SQL_TOOLS:
        return keys
    _params = params or {}
    if (_params.get("connection_type") or "sqlite") == "sqlite":
        p = _params.get("path", "")
        if p and isinstance(p, str):
            keys.add(_canonical_path(p))
    else:
        conn_str = _params.get("connection_string", "")
        if conn_str and isinstance(conn_str, str):
            keys.add(_db_key(conn_str))
    return keys



# ════════════════════════════════════════════════════════════
# 冲突检测（复制自 action_handler.py）
# ════════════════════════════════════════════════════════════

def _has_conflict(all_calls: List[Dict]) -> bool:
    """检测路径/窗口冲突 — 北京老陈 2026-07-04 初版; 小欧 2026-08-09 计数版; 小欧 2026-08-11 窗口工具纳入
    冲突：同一键(文件路径/窗口标题/数据库)被>=2次调用访问, 且(至少一个写操作 或 含窗口工具)
    有冲突→顺序执行, 无冲突→并行; 同库 execute_sql 计为写操作 — 小欧 2026-10-19
    完整复制自 action_handler.py
    """
    path_ops: Dict[str, Dict[str, Any]] = {}

    def _record(_path: str, _name: str) -> None:
        entry = path_ops.setdefault(_path, {"count": 0, "tools": set()})
        entry["count"] += 1
        entry["tools"].add(_name)

    for c in all_calls:
        name = _tool_name_of(c)
        if name not in FILE_OPERATION_TOOLS and name not in WINDOW_TARGET_TOOLS and name not in _SQL_TOOLS:
            continue
        for _path in _conflict_keys(name, c.get("tool_params", {})):
            _record(_path, name)

    for path, entry in path_ops.items():
        tools = entry["tools"]
        if entry["count"] >= 2 and (any(t in _WRITE_OPS for t in tools) or any(t in WINDOW_TARGET_TOOLS for t in tools)):
            logger.info(f"[_has_conflict] 操作冲突(路径/窗口/数据库): {path}, tools={tools}, 调用数={entry['count']}, 降级顺序执行")
            return True
    return False


# ════════════════════════════════════════════════════════════
# 并查集分组（复制自 action_handler.py）
# ════════════════════════════════════════════════════════════

def _partition_calls(all_calls: List[Dict]) -> List[List[int]]:
    """按路径/窗口/数据库相关性分组(并查集连通分量): 共享键的调用归一组, 组间无共享→可并行
    返回: 组列表, 每组是 all_calls 的索引列表 — 小欧 2026-08-09 — 小欧 2026-08-11 窗口工具自动纳入
    SQL 同库调用经 _conflict_keys 并入同一组 — 小欧 2026-10-19
    完整复制自 action_handler.py
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
        for p in _conflict_keys(_tool_name_of(c), c.get("tool_params", {})):
            path_to_calls.setdefault(p, []).append(i)
    for _p, idxs in path_to_calls.items():
        base = idxs[0]
        for i in idxs[1:]:
            _union(base, i)

    groups = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)
    return list(groups.values())
