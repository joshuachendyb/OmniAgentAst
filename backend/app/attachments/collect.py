# 编辑历史:
# 2026-11-04 小欧 新建: 产物「存为附件」——工作区内只引用, 工作区外复制固化 — 小欧-2026-11-04
# 2026-11-06 小欧 改名 import: service → attachment_service(模块改名对齐命名惯例) — 小欧-2026-11-06
# 2026-11-06 小欧 溯源改造: collect_artifact 加可选 task_id, copied 时透传 save_bytes 写入 source_task_id 溯源 — 小欧-2026-11-06

"""attachments.collect — 概览产出物「存为附件」。

判定口径: 用**会话工作区表**判产物在不在工作区, 不用 ContextVar 快照 ——
  get_ws_snapshot() 只在 agent 任务执行期有值, HTTP 请求期恒 None,
  用它判定会让所有产物都走复制(错), 且无法解释"为什么点了两次多出两份"。

两种结果:
  referenced  产物已在会话工作区 → 不复制, 直接回引用路径(前端走 quoteFile)
  copied      产物在工作区外   → 复制进 {默认工作区}/attachments/ 并登记
"""
from pathlib import Path
from typing import Any

from app.attachments import attachment_service as attach
from app.db import db
from app.file_browse import browse_service as browse
from app.file_browse.errors import (
    ATTACHMENT_TOO_LARGE,
    NOT_FOUND,
    SESSION_NOT_FOUND,
    fail,
)


def _workspace_paths(session_id: str) -> list[Path]:
    """会话工作区根(库为真源); 单条坏路径不影响其余判定。"""
    with db.get_conn("chat") as conn:
        rows = conn.execute(
            "SELECT path FROM chat_session_workspaces WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    out: list[Path] = []
    for r in rows:
        raw = r[0] if isinstance(r, (tuple, list)) else r["path"]
        if raw:
            out.append(Path(raw).resolve())
    return out


def _resolve_source(source_path: str) -> Path:
    """产物路径 → 绝对路径。根内相对走唯一解析, 盘符绝对走外部口径。"""
    raw = (source_path or "").strip()
    if not raw:
        fail(NOT_FOUND, "缺少产物路径")
    if browse._is_abs_drive_path(raw):
        target = Path(raw)
    else:
        target, _rel = browse._resolve_within_root(raw)   # 越界/非法 → 403/400
    if not target.is_file():
        fail(NOT_FOUND, "产物不存在或已移动")
    return target.resolve()


def collect_artifact(session_id: str, source_path: str,
                     task_id: str | None = None) -> dict[str, Any]:
    """唯一入口。返回 {mode, path, label, size} 或 {mode, attachment}。

    task_id 可选溯源: 产物「存为附件」时记录来源任务(会话级主归属不变)。
      referenced(不落库)恒不需要; copied 时透传给 save_bytes 写入 source_task_id。
    """
    if not session_id:
        fail(SESSION_NOT_FOUND)
    with db.get_conn("chat") as conn:
        if not conn.execute(
            "SELECT 1 FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone():
            fail(SESSION_NOT_FOUND)

    target = _resolve_source(source_path)
    for ws in _workspace_paths(session_id):
        try:
            target.relative_to(ws)
        except ValueError:
            continue
        st = target.stat()
        return {"mode": "referenced",
                "path": attach.rel_to_root(str(target)),
                "label": target.name, "size": st.st_size}

    st = target.stat()
    if st.st_size > attach.MAX_FILE_BYTES:
        fail(ATTACHMENT_TOO_LARGE)
    data = target.read_bytes()
    if len(data) > attach.MAX_FILE_BYTES:
        fail(ATTACHMENT_TOO_LARGE)
    rec = attach.save_bytes(session_id, target.name, data,
                            source_path=str(target),
                            source_task_id=task_id)
    return {"mode": "copied", "attachment": rec}
