# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 - 小欧 - 架构边界修正(三堂会审): 会话信任读写三函数从 app/services/chat/storage.py
#   迁入本层 app/tools/trust_db.py —— 修复 app/tools 禁 app.services 依赖方向守护违规
#   (test_architecture_boundaries.py test_layer_boundaries 报 trust.py imports app.services.chat.storage)。
#   原逻辑逐字复制不改业务(能复制不重写): get_session_id_by_task/check_session_trust/insert_session_trust
#   + _norm_trust_path(储storage侧 delete/list 仍使用, 双侧各持一份保持落库/查询一致)。
#   迁移后 trust.py 由 import app.services.chat.storage 改为 import app.tools.trust_db(同层, 零越层)。
"""tools 层会话信任读写(纯 SQL 查询, 不依赖 services 层) — 小欧 2026-09-05"""
from pathlib import Path
from typing import Optional
from sqlite3 import Connection

from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z入库


def _norm_trust_path(path: Optional[str]) -> Optional[str]:
    """信任路径规范化(resolve 绝对化, 供落库/查询双侧一致) — 小欧 2026-09-02"""
    if not path:
        return None
    try:
        return str(Path(path).resolve())
    except Exception:
        return None


def insert_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None) -> None:
    """HITL"信任本次会话"落库（UNIQUE(session_id, tool_name, path) 幂等）— 小欧 2026-08-16; v1.5 增 path 参数
    path=None=无路径工具的工具级通配; 非空=该路径及子目录树递归豁免"""
    conn.execute(
        "INSERT OR IGNORE INTO chat_session_trust(session_id, tool_name, path, created_at) VALUES (?,?,?,?)",
        (session_id, tool_name, _norm_trust_path(path), get_local_iso_timestamp()),
    )


def check_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None) -> bool:
    """工具安全检查豁免查询：会话已信任该 tool+path 则免二次 HITL 确认 — 小欧 2026-08-16; v1.5 增 path 前缀递归匹配
    匹配规则(北京老陈 2026-09-02 定案):
      path=None: 仅命中工具级通配行(path IS NULL);
      path 给定: 命中工具级通配行, 或任一行信任路径等于/为目标的父目录(前缀递归, 与 temp_auth 语义对齐)。"""
    rows = conn.execute(
        "SELECT path FROM chat_session_trust WHERE session_id=? AND tool_name=?",
        (session_id, tool_name),
    ).fetchall()
    if path is None:
        return any(r["path"] is None for r in rows)
    target = _norm_trust_path(path)
    if target is None:
        return False
    target_p = Path(target)
    for r in rows:
        p = r["path"]
        if p is None:
            return True  # 工具级通配行: 任意路径命中
        trusted_p = Path(p)
        if trusted_p == target_p or trusted_p in target_p.parents:
            return True  # 前缀递归: 信任根等于目标 或 为目标祖先目录
    return False


def get_session_id_by_task(conn: Connection, task_id: str) -> Optional[str]:
    """按 task_id 反查 session_id（chat_tasks 已建行时）— HITL trust 落库/豁免用, 禁止伪 agent.session_id — 小欧 2026-08-16"""
    row = conn.execute(
        "SELECT session_id FROM chat_tasks WHERE task_id=?",
        (task_id,),
    ).fetchone()
    return row["session_id"] if row else None