# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: trust 三合一提取下沉, 解环 action_handler → trust 单向依赖 - 小健-2026-09-04
"""
trust — 信任域三合一: 路径解析 + 信任路径提取 + 信任跳过判定 + 信任落库

从 action_handler.py 提取:
- _parse_paths: 路径/窗口冲突键解析（纯函数）
- extract_trust_path: 信任落库/查询的目标路径提取（纯函数）
- resolve_skip: 会话级信任查询, 决定是否跳过HITL确认（async）

从 hitl_confirmation.py 提取:
- save_session_trust: 用户确认后将工具+路径写入会话信任记录（async）

原则: 完整复制, 保留原始功能分支和逻辑, 禁止简化退化
"""
from typing import Dict, Optional, Set
from app.tools.tools_alias_mapper import PARAM_ALIASES, normalize_tool_name
from app.tools.tool_constants import FILE_OPERATION_TOOLS

# 窗口类目标工具集合（冲突检测用）— 小欧 2026-08-11 task002 三堂会审修复A
# 窗口状态变更(restore/resize/focus)作用于同一窗口时非幂等, 同批并行会产生竞态
# 不含 window_info(只读枚举, 不改变窗口状态, 无竞态)。
WINDOW_TARGET_TOOLS = {"window_focus", "window_resize", "set_window_state"}


# ════════════════════════════════════════════════════════════
# 纯函数：路径解析（复制自 action_handler.py:551-578）
# ════════════════════════════════════════════════════════════

def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径/窗口冲突键集合(复用 PARAM_ALIASES 别名→规范名) — 小欧 2026-08-09 — 小欧 2026-08-11 窗口分支
    文件工具: 解析 path 集合(与 _has_conflict/_partition_calls 共用, DRY)。
    窗口工具: 以 "window:{window_title}" 为冲突键, 同标题窗口工具并入同组串行(状态变更非幂等);
              缺 window_title 返回空集——窗口工具参数校验必失败, 不会操作任何窗口, 无竞态风险, 不参与分组。
    完整复制自 action_handler.py:551-578，保留别名映射逻辑，禁止简化退化
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
# 纯函数：信任路径提取（复制自 action_handler.py:581-587）
# ════════════════════════════════════════════════════════════

def extract_trust_path(name: str, params: Dict) -> Optional[str]:
    """提取工具调用用于信任落库/查询的目标路径(复用 _parse_paths, DRY) — 小欧 2026-09-02
    取首个非 window: 键的文件路径; 无路径参数/窗口工具/提取失败返回 None(=工具级通配)
    完整复制自 action_handler.py:581-587，取首个非 window: 键的文件路径
    """
    for p in _parse_paths(name, params or {}):
        if not p.startswith("window:"):
            return p
    return None


# ════════════════════════════════════════════════════════════
# async函数：信任跳过判定（复制自 action_handler.py:297-327）
# ════════════════════════════════════════════════════════════

async def resolve_skip(agent_task_id: str, tool_name: str, params: dict) -> bool:
    """信任跳过判定: 查询会话级信任记录,决定是否跳过HITL确认
    完整复制自 action_handler.py:297-327（check_safety_and_confirm内联逻辑提取）
    """
    from app.db import db
    from app.tools.trust_db import get_session_id_by_task, check_session_trust
    try:
        _sid = await db.atxn("chat", lambda conn: get_session_id_by_task(conn, agent_task_id))
    except Exception:
        return False
    if not _sid:
        return False
    _tgt = extract_trust_path(tool_name, params)
    try:
        return await db.atxn("chat", lambda conn: check_session_trust(conn, _sid, normalize_tool_name(tool_name), _tgt))
    except Exception as _te:
        from app.logger import logger
        logger.warning(f"[trust] 会话信任查询失败: task={agent_task_id}, tool={tool_name}, err={_te}")
        return False


# ════════════════════════════════════════════════════════════
# async函数：信任落库（复制自 hitl_confirmation.py:184-200）
# ════════════════════════════════════════════════════════════

async def save_session_trust(task_id: str, tool_name: str, path) -> None:
    """会话信任落库: 用户确认后将工具+路径写入会话信任记录
    完整复制自 hitl_confirmation.py:184-200（resolve_confirmation内联逻辑提取）
    """
    from app.db import db
    from app.tools.trust_db import get_session_id_by_task, insert_session_trust
    from app.logger import logger

    def _do(conn):
        _sid = get_session_id_by_task(conn, task_id)
        if not _sid:
            raise ValueError(f"[HITL] task_id={task_id} 无 session_id 可反查,信任禁止落库")
        insert_session_trust(conn, _sid, normalize_tool_name(tool_name), path)

    await db.atxn("chat", _do)
    logger.info(f"[HITL] 会话信任落库: task_id={task_id}, tool_name={normalize_tool_name(tool_name)}")
