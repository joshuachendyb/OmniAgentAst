# 编辑历史:
# 2026-11-04 小欧 新建: 附件域服务(上传落盘/登记/查询/删除/默认工作区定位) — 小欧-2026-11-04
# 2026-11-06 小欧 改名 service.py→attachment_service.py: 与系统 *_service.py 命名惯例对齐(名实相符),
#   消费方 import 路径同步(`from app.attachments import attachment_service`) — 小欧-2026-11-06
# 2026-11-06 小欧 方案B: 增 source_task_id 溯源列(产物「存为附件」来源任务); save_bytes 加可选入参,
#   会话级主归属不变, 仅溯源且不进去重键 — 小欧-2026-11-06

"""attachments.attachment_service — 附件落盘与登记（唯一写盘点）。

落盘位置: {会话默认工作区}/attachments/
  默认工作区只认 chat_session_workspaces.is_default=1; 无默认行时调
  reconcile_session_workspaces 补建(幂等), 不猜目录名。

安全纪律:
  1. 存储路径只由服务端计算, 请求体不承载任何目标路径(防穿越);
  2. 文件名 sanitize(分隔符/控制字符/Windows 保留名/首尾点);
  3. 落盘或登记任一步失败, 立即清理半成品文件(不留垃圾);
  4. 写盘与类型探测一律 asyncio.to_thread 卸载, 不阻塞事件循环。
"""
import asyncio
import hashlib
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.attachments import extract
from app.config import get_config
from app.db import db
from app.file_browse import browse_service as browse
from app.file_browse.errors import (
    ATTACHMENT_TOO_LARGE,
    ATTACHMENT_UNAVAILABLE,
    NOT_FOUND,
    SESSION_NOT_FOUND,
    UNSUPPORTED_TYPE,
    fail,
)
from app.logger import logger
from app.services.chat.workspace_service import reconcile_session_workspaces
from app.utils.time_utils import get_local_iso_timestamp

# ── 配额 ────────────────────────────────────────────────────────────────
MAX_IMAGE_BYTES = browse.MAX_IMAGE_BYTES        # 10MB: 直接引用图片预览口径, 不重写数值(DRY)
MAX_FILE_BYTES = 20 * 1024 * 1024               # 非图片单文件上限
MAX_SESSION_BYTES = 200 * 1024 * 1024           # 单会话附件总量上限

_ATTACH_SUBDIR = "attachments"
_COLS = ("id, session_id, original_name, stored_path, mime, size, sha256, kind, "
         "extract_status, extract_chars, source_path, source_task_id, created_at")

# 上传白名单 = extract 五分类词典的组合(类型轴唯一真源, 免两份名单漂移)。
# 视频后缀 S0 即放行(可传可发, 注入走档案卡); 纯 binary(.zip/.exe 等)一律 415。
_ALLOWED_SUFFIXES = (extract.IMAGE_SUFFIXES | extract.VIDEO_SUFFIXES
                     | extract.RICH_SUFFIXES | extract.TEXT_SUFFIXES)

_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _sanitize_name(name: str) -> str:
    """文件名 sanitize: 去目录段/非法字符/保留名, 限长 120。"""
    base = Path((name or "").replace("\\", "/")).name
    base = _BAD_CHARS.sub("_", base).strip().strip(".")
    if not base:
        return "file"
    parts = base.rsplit(".", 1)
    stem = parts[0]
    ext = f".{parts[1]}" if len(parts) == 2 else ""
    if stem.upper() in _RESERVED_NAMES:
        stem = f"_{stem}"
    stem = (stem[:100] or "file")
    ext = ext[:20]
    return f"{stem}{ext}"


def rel_to_root(stored_path: str) -> str:
    """绝对路径 → 当前项目根相对 posix 路径(上行 refs 用)。根外/异常回落 posix 绝对路径。"""
    try:
        root = Path(get_config().get_project_root()).resolve()
        return Path(stored_path).resolve().relative_to(root).as_posix()
    except Exception:  # noqa: BLE001 — 取不到根不影响附件本身可用
        return Path(stored_path).as_posix()


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(zip([c.strip() for c in _COLS.split(",")], tuple(row)))
    d["path"] = rel_to_root(d["stored_path"])
    return d


def _default_ws_path(conn: Any, session_id: str) -> str | None:
    row = conn.execute(
        "SELECT path FROM chat_session_workspaces "
        "WHERE session_id = ? AND is_default = 1 LIMIT 1",
        (session_id,),
    ).fetchone()
    return row[0] if row else None


def ensure_session_attachment_dir(session_id: str) -> Path:
    """附件目录唯一解析函数: 默认工作区 + attachments 子目录。"""
    with db.get_conn("chat") as conn:
        ws = _default_ws_path(conn, session_id)
        if not ws:
            # 首次进入 / 用户删掉默认区 / 项目根已变 → 幂等补建(不猜目录名)
            reconcile_session_workspaces(conn, session_id)
            ws = _default_ws_path(conn, session_id)
    if not ws:
        fail(ATTACHMENT_UNAVAILABLE, "会话默认工作区创建失败，无法落盘附件")
    folder = Path(ws) / _ATTACH_SUBDIR
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"[attachments] mkdir failed dir={folder} err={e}")
        fail(ATTACHMENT_UNAVAILABLE, "附件目录不可写，请检查会话工作区")
    return folder


def save_bytes(session_id: str, name: str, data: bytes, *,
               mime: str | None = None,
               source_path: str | None = None,
               source_task_id: str | None = None) -> dict[str, Any]:
    """落盘 + 登记唯一实现（上传 / 存为附件共用）。

    data 已在内存（单文件 ≤20MB），一次性读写比分块流式少一半分支（KISS）。
    source_path 仅记录来源（上传为 None），不参与任何路径裁决。
    source_task_id 溯源产物「存为附件」的来源任务(会话级主归属不变, 仅溯源),
      不进去重键——同会话同内容复用旧行时沿用首条 source_task_id。
    """
    if not session_id:
        fail(NOT_FOUND, "缺少 session_id")
    with db.get_conn("chat") as conn:
        if not conn.execute(
            "SELECT 1 FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone():
            fail(SESSION_NOT_FOUND)

    safe = _sanitize_name(name)
    suffix = Path(safe).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        fail(UNSUPPORTED_TYPE, "该文件类型暂不支持（支持图片、文本、PDF、Word、Excel、PowerPoint、视频；纯二进制如 zip/exe 仅可经「存为附件」进入）")

    size = len(data)
    if size > (MAX_IMAGE_BYTES if suffix in extract.IMAGE_SUFFIXES else MAX_FILE_BYTES):
        fail(ATTACHMENT_TOO_LARGE)

    sha = hashlib.sha256(data).hexdigest()
    with db.get_conn("chat") as conn:
        dup = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE session_id = ? AND sha256 = ? LIMIT 1",
            (session_id, sha),
        ).fetchone()
        if dup:
            return _row_to_dict(dup)
        used = conn.execute(
            "SELECT COALESCE(SUM(size), 0) FROM attachments WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        if int(used) + size > MAX_SESSION_BYTES:
            fail(ATTACHMENT_TOO_LARGE, "会话附件总量超过 200MB，请先清理旧附件")

    folder = ensure_session_attachment_dir(session_id)
    stamp = get_local_iso_timestamp().replace("-", "").replace(":", "").replace("T", "-")[:15]
    stored = folder / f"{stamp}-{sha[:8]}-{safe}"
    try:
        stored.write_bytes(data)
        kind = extract.classify(stored, mime or "", size)
        att_id = uuid.uuid4().hex
        with db.get_conn("chat") as conn:
            # INSERT OR IGNORE + 回查: UNIQUE(session_id, sha256) 约束防并发竞态(Agnes 补)
            conn.execute(
                f"INSERT OR IGNORE INTO attachments ({_COLS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (att_id, session_id, safe, str(stored),
                 mime or mimetypes.guess_type(safe)[0] or "application/octet-stream",
                 size, sha, kind, "none", 0, source_path, source_task_id,
                 get_local_iso_timestamp()),
            )
    except Exception:
        stored.unlink(missing_ok=True)
        raise
    rec = get_attachment(att_id)
    if rec is None:
        # INSERT OR IGNORE 未写入(并发同 sha 已存在) → 先删本次写出的孤儿文件, 再回查
        stored.unlink(missing_ok=True)
        with db.get_conn("chat") as conn:
            dup = conn.execute(
                f"SELECT {_COLS} FROM attachments WHERE session_id = ? AND sha256 = ? LIMIT 1",
                (session_id, sha),
            ).fetchone()
        if dup:
            return _row_to_dict(dup)
        fail(ATTACHMENT_UNAVAILABLE, "附件登记后读取失败")
    return rec


async def save_upload(session_id: str, upload: UploadFile) -> dict[str, Any]:
    """HTTP 上传入口：读入内存后交给 save_bytes（磁盘 IO 卸载到线程）。"""
    data = await upload.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        fail(ATTACHMENT_TOO_LARGE)
    return await asyncio.to_thread(
        save_bytes, session_id, upload.filename or "file", data,
        mime=upload.content_type,
    )


def list_attachments(session_id: str) -> list[dict[str, Any]]:
    with db.get_conn("chat") as conn:
        rows = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_attachment(attachment_id: str) -> dict[str, Any] | None:
    """按 id 取单条(同步: resolver 在 to_thread 内调用)。"""
    if not attachment_id:
        return None
    with db.get_conn("chat") as conn:
        row = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_attachment(attachment_id: str, purge: bool = False) -> None:
    """删记录; purge=True 时同时删磁盘文件(默认不删, 防误删)。

    删除顺序修复: purge=True 时**先删磁盘文件、成功后才删 DB 行** ——
    若磁盘删失败则不删行并抛错, 避免"记录已删、文件成孤儿"。不 purge 时仅删行(磁盘留档)。
    """
    with db.get_conn("chat") as conn:
        row = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        if not row:
            fail(NOT_FOUND, "附件不存在")
        if purge:
            try:
                Path(row["stored_path"]).unlink(missing_ok=True)
            except OSError as e:
                logger.error(f"[attachments] purge 失败, 记录保留 id={attachment_id} err={e}")
                fail(ATTACHMENT_UNAVAILABLE, "附件磁盘删除失败，记录已保留")
        conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))


def read_inject_text(attachment_id: str) -> str:
    """预览端点数据源: 与 resolver 同一条生成路径, 不产生第二套口径。"""
    att = get_attachment(attachment_id)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    return extract.build_inject_text(att)
