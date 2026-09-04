# -*- coding: utf-8 -*-
# 编辑历史: 2026-09-03 小欧 - 新建: trust 提取下沉，解环 - 小欧-2026-09-03
# 编辑历史: 2026-09-04 小健 - 合并: trust_utils+trust_service+trust_repository三合一为trust.py - 小健-2026-09-04
from typing import Dict, Optional, Set
from app.tools.tools_alias_mapper import PARAM_ALIASES, normalize_tool_name
from app.tools.tool_constants import FILE_OPERATION_TOOLS

WINDOW_TARGET_TOOLS = {"window_focus", "window_resize", "set_window_state"}

# ════════════════════════════════════════════════════════════
# 纯函数：路径解析（复制自 action_handler.py:551-578）
# ════════════════════════════════════════════════════════════

def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径/窗口冲突键集合(复用 PARAM_ALIASES 别名→规范名)
    完整复制自 action_handler.py:551-578，保留别名映射逻辑，禁止简化退化"""
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

def extract_trust_path(name: str, params: Dict) -> Optional[str]:
    """提取工具调用用于信任落库/查询的目标路径(复用 _parse_paths, DRY)
    完整复制自 action_handler.py:581-587，取首个非 window: 键的文件路径"""
    for p in _parse_paths(name, params or {}):
        if not p.startswith("window:"):
            return p
    return None

# ════════════════════════════════════════════════════════════
# async函数：信任跳过判定（复制自 action_handler.py:297-327）
# ════════════════════════════════════════════════════════════

async def resolve_skip(agent_task_id: str, tool_name: str, params: dict) -> bool:
    """信任跳过判定: 查询会话级信任记录,决定是否跳过HITL确认"""
    from app.db import db
    from app.services.chat.storage import get_session_id_by_task, check_session_trust
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
# async函数：信任落库（复制自 hitl_confirmation.py:184-196）
# ════════════════════════════════════════════════════════════

async def save_session_trust(task_id: str, tool_name: str, path: str | None):
    """会话信任落库: 用户确认后将工具+路径写入会话信任记录"""
    from app.db import db
    from app.services.chat.storage import get_session_id_by_task, insert_session_trust
    def _do(conn):
        _sid = get_session_id_by_task(conn, task_id)
        if not _sid:
            raise ValueError(f"[HITL] task_id={task_id} 无 session_id 可反查,信任禁止落库")
        insert_session_trust(conn, _sid, normalize_tool_name(tool_name), path)
    await db.atxn("chat", _do)
