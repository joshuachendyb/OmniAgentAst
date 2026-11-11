# 编辑历史:
# 2026-11-04 小欧 新建: 附件域服务(上传落盘/登记/查询/删除/默认工作区定位) — 小欧-2026-11-04
# 2026-11-06 小欧 改名 service.py→attachment_service.py: 与系统 *_service.py 命名惯例对齐(名实相符),
#   消费方 import 路径同步(`from app.attachments import attachment_service`) — 小欧-2026-11-06
# 2026-11-06 小欧 溯源改造: 增 source_task_id 溯源列(产物「存为附件」来源任务), save_bytes 加可选入参,
#   会话级主归属不变, 仅溯源且不进去重键 — 小欧-2026-11-06
# 2026-11-06 小欧 修复: _sanitize_name 去首尾点 strip(".")→rstrip(".") —— 原实现剥掉开头点,
#   破坏 .env/.dockerfile 点文件扩展名(白名单内却 415), 白名单口径分叉 — 小欧-2026-11-06

# 2026-11-07 小欧 修复: save_upload 初始读限按后缀分档(图片 10MB/其他 20MB),
#   原统一读 MAX_FILE_BYTES+1, 12MB 图片被完整读入内存后才被拒, 白占堆 — 小欧-2026-11-07
# 2026-11-07 小欧 越权收紧: 增 get_attachment_scoped 会话作用域校验(不匹配视同不存在), delete/read_inject_text
#   加 session_id 必填 —— 附件是会话级资产, 跨会话按 id 直取属越权(resolver 同步收紧) — 小欧-2026-11-07
# 2026-11-07 小欧 修复: delete_attachment(purge=True) 级联清理 material_pack_items 中引用同 stored_path 的
#   条目 —— 原只删附件记录+磁盘文件, 素材包条目仍存旧 path, 投喂时找不到 → 红底失效 — 小欧-2026-11-07
# 2026-11-07 小欧 资产台账: attachments 升格(scope/last_used_at/use_count); 增 promote_attachment、
#   list 多作用域/重命名/清最近/发送注入记账; delete 改按路径引用计数删文件, 被合集引用 409 需 force 确认 — 小欧-2026-11-07
# 2026-11-07 小欧 预览严格读: /text 改严格校验不再自动收藏, auto_promote 只留发送注入(resolver)与手动/引用链
#   —— 读路径不产生任何写副作用, 尊重会话越权收紧 — 小欧-2026-11-07
# 2026-11-07 小欧 注释清理: 去除文档号/章节号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
# 2026-11-07 小欧 - favorited/global_id 收口 _decorate_global 单一实现(单条/列表同口径);
#   delete 合集条目匹配改 attachment_id + rel_to_root 相对路径为真、原绝对 path 子句永假;
#   list 非法 scope 由静默回落改 fail(INVALID_PARAM) — 小欧-2026-11-07
# 2026-11-07 小欧 - 左栏标签对准: session 作用域排除任务产物溯源行(stid 非空归属 ai 栏), 消双栏重叠显示 — 小欧-2026-11-07
# 2026-11-09 小欧 S3: 增 mark_extract_result 抽取态回填(首次成功/失败写 extract_status/extract_chars) — 小欧-2026-11-09
# 2026-11-10 小欧 - read_inject_text 抽取失败兜底: S3改抛异常后预览路径漏改, 富文档/空工作簿抽取异常直穿HTTP 500;
#   降级为错误说明文本(纯读契约不变, 不回填抽取态), 与resolver失败折算同口径
# 2026-11-11 小欧 - 增 reextract 真抽取手动重跑: 重置抽取态后按契约文本出口重算回填
#   (仅 fallback_quality=content 的 kind, 失败折算 failed 不抛异常) — 小欧-2026-11-11



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
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.attachments import extract
from app.config import get_config
from app.db import db
from app.db.database import resolve_db_dir
from app.file_browse import browse_service as browse
from app.file_browse.errors import (
    ATTACHMENT_IN_USE,
    ATTACHMENT_NOT_AVAILABLE,
    ATTACHMENT_TOO_LARGE,
    ATTACHMENT_UNAVAILABLE,
    INVALID_PARAM,
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
MAX_LIST_ITEMS = 200                            # 「最近用过 / 已收藏」单次上限(抽屉一屏够用)

_ATTACH_SUBDIR = "attachments"
_ASSETS_SUBDIR = "assets"
_COLS = ("id, session_id, original_name, stored_path, mime, size, sha256, kind, "
         "extract_status, extract_chars, source_path, source_task_id, created_at, "
         "scope, last_used_at, use_count")
# 新行只写前 13 列: scope/last_used_at/use_count 由表默认值给出(session/None/0)
_INSERT_COLS = ("id, session_id, original_name, stored_path, mime, size, sha256, kind, "
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
    """文件名 sanitize: 去目录段/非法字符/保留名, 限长 120。

    2026-11-06 小欧: 去首尾点改用 rstrip(".") 仅去**结尾点** —— 原实现 strip(".") 把开头点一起剥掉,
    破坏 .env/.dockerfile 点文件扩展名使其即便在白名单内也无法上传(415), 白名单口径分叉; 修正后保留开头点。
    """
    base = Path((name or "").replace("\\", "/")).name
    base = _BAD_CHARS.sub("_", base).strip().rstrip(".")
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
    # 2026-11-07 小欧: 磁盘文件是否还在(失效行仍可删/可重命名, 但不可加入本轮)
    d["available"] = Path(d["stored_path"]).is_file()
    d["favorited"] = False
    d["global_id"] = None
    return d


def _decorate_global(conn: Any, items: list[dict[str, Any]]) -> None:
    """favorited/global_id 唯一裁决点: 本行是 global 即收藏, 否则看同 sha 的全局行。"""
    shas = sorted({i["sha256"] for i in items if i["scope"] != "global"})
    gmap: dict[str, str] = {}
    if shas:
        marks = ",".join("?" * len(shas))
        gmap = {
            r["sha256"]: r["id"] for r in conn.execute(
                "SELECT sha256, id FROM attachments "
                f"WHERE scope = 'global' AND sha256 IN ({marks})", shas)
        }
    for it in items:
        gid = it["id"] if it["scope"] == "global" else gmap.get(it["sha256"])
        it["favorited"] = gid is not None
        it["global_id"] = gid


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
            d = _row_to_dict(dup)
            _decorate_global(conn, [d])
            return d
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
                f"INSERT OR IGNORE INTO attachments ({_INSERT_COLS}) "
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
            d = _row_to_dict(dup)
            _decorate_global(conn, [d])
            return d
        fail(ATTACHMENT_UNAVAILABLE, "附件登记后读取失败")
    return rec


async def save_upload(session_id: str, upload: UploadFile) -> dict[str, Any]:
    """HTTP 上传入口：读入内存后交给 save_bytes（磁盘 IO 卸载到线程）。

    初始读限按后缀分档: 图片只读 10MB+1, 超限图片在读入阶段即拒,
    不再统一读 20MB+1 白占堆; 无扩展名/其他后缀仍按 20MB 读,
    类型与最终大小裁决归 save_bytes(单一真源不变)。
    """
    suffix = Path(upload.filename or "").suffix.lower()
    limit = MAX_IMAGE_BYTES if suffix in extract.IMAGE_SUFFIXES else MAX_FILE_BYTES
    data = await upload.read(limit + 1)
    if len(data) > limit:
        fail(ATTACHMENT_TOO_LARGE)
    return await asyncio.to_thread(
        save_bytes, session_id, upload.filename or "file", data,
        mime=upload.content_type,
    )


_SCOPE_FILTER = {
    # 本会话: 会话归属行, 排除任务产物溯源行(归 ai 栏)消双栏重叠; global 行 session_id 恒 NULL 天然不进本栏
    "session": ("session_id = ? AND (source_task_id IS NULL OR source_task_id = '')", "created_at DESC"),
    # 最近用过: 发送注入过(use_count>0), 跨会话共享
    "recent": ("use_count > 0", "last_used_at DESC"),
    # 已收藏: 全局资产
    "global": ("scope = 'global'", "COALESCE(last_used_at, created_at) DESC"),
    # 任务产物(scope 键沿用 ai): 「存为附件」copied 模式的溯源行
    "ai": ("source_task_id IS NOT NULL AND source_task_id <> ''", "created_at DESC"),
}


def list_attachments(session_id: str | None = None, *, scope: str = "session",
                     q: str | None = None, limit: int = MAX_LIST_ITEMS,
                     offset: int = 0) -> list[dict[str, Any]]:
    """附件列表（作用域唯一实现）— 小欧-2026-11-07

    scope: session(本会话) / recent(最近用过) / global(已收藏) / ai(任务产物)。
    每行补 favorited/global_id（同 sha 的全局行 id），前端据此 1 击收藏/取消收藏。
    """
    scope_row = _SCOPE_FILTER.get(scope)
    if not scope_row:
        fail(INVALID_PARAM, "scope 只支持 session / recent / global / ai")
    where, order = scope_row
    params: list[Any] = []
    if scope == "session":
        if not session_id:
            return []
        params.append(session_id)
    if q and q.strip():
        where += " AND original_name LIKE ?"
        params.append(f"%{q.strip()}%")
    limit = max(1, min(int(limit or MAX_LIST_ITEMS), MAX_LIST_ITEMS))
    offset = max(0, int(offset or 0))
    with db.get_conn("chat") as conn:
        if scope == "session" and not conn.execute(
            "SELECT 1 FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone():
            return []      # 会话不存在返回空(附件随 session 级联删, 无孤儿数据)
        rows = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE {where} "
            f"ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        items = [_row_to_dict(r) for r in rows]
        _decorate_global(conn, items)
    return items


def assets_dir() -> Path:
    """全局资产目录: {data_dir}/assets/{YYYYMM}（不能放会话工作区, 会话删除会带走）。"""
    folder = resolve_db_dir() / _ASSETS_SUBDIR / get_local_iso_timestamp()[:7].replace("-", "")
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"[attachments] assets mkdir failed dir={folder} err={e}")
        fail(ATTACHMENT_UNAVAILABLE, "全局资产目录不可写")
    return folder


def promote_attachment(attachment_id: str) -> dict[str, Any] | None:
    """升级为全局资产（幂等 + sha 去重）— 小欧-2026-11-07

    跨会话引用与手动 ☆ 共用本实现：复制到 assets/ 后建 scope='global' 行
    （session_id 恒 NULL，会话删除不影响）。同 sha 已有全局行时直接复用，不再复制。
    """
    att = get_attachment(attachment_id)
    if not att:
        return None
    if att["scope"] == "global":
        return att
    with db.get_conn("chat") as conn:
        dup = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE scope = 'global' AND sha256 = ? LIMIT 1",
            (att["sha256"],),
        ).fetchone()
    if dup:
        d = _row_to_dict(dup)
        _decorate_global(conn, [d])
        return d
    src = Path(att["stored_path"])
    if not src.is_file():
        fail(ATTACHMENT_NOT_AVAILABLE)
    dest = assets_dir() / f"{att['sha256'][:16]}-{_sanitize_name(att['original_name'])}"
    new_id = uuid.uuid4().hex
    try:
        if not dest.exists():
            shutil.copy2(src, dest)
        with db.get_conn("chat") as conn:
            conn.execute(
                f"INSERT OR IGNORE INTO attachments ({_INSERT_COLS}, scope) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'global')",
                (new_id, None, att["original_name"], str(dest), att["mime"],
                 att["size"], att["sha256"], att["kind"], att["extract_status"],
                 att["extract_chars"], att["source_path"], att["source_task_id"],
                 att["created_at"]),
            )
    except Exception:
        logger.exception(f"[attachments] promote 失败 id={attachment_id}")
        fail(ATTACHMENT_UNAVAILABLE, "收藏失败，请稍后重试")
    rec = get_attachment(new_id)
    if rec is None:
        # 并发 promote: 另一请求先插入同 sha 全局行 → 复用本次结果
        with db.get_conn("chat") as conn:
            dup = conn.execute(
                f"SELECT {_COLS} FROM attachments WHERE scope = 'global' AND sha256 = ? LIMIT 1",
                (att["sha256"],),
            ).fetchone()
        if dup:
            # 仅当幸存行不指向本文件时才清理本次副本(同 sha 同名时 dest 必然相同, 删了就是删幸存行)
            if dup["stored_path"] != str(dest):
                dest.unlink(missing_ok=True)
            d = _row_to_dict(dup)
            _decorate_global(conn, [d])
            return d
        fail(ATTACHMENT_UNAVAILABLE, "收藏失败，请稍后重试")
    return rec


def rename_attachment(attachment_id: str, name: str,
                      session_id: str | None) -> dict[str, Any]:
    """重命名（只改展示名, 不动磁盘文件名 —— 同名多行共享路径时改文件名会互相打断）。"""
    att = get_attachment_scoped(attachment_id, session_id)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    safe = _sanitize_name(name)
    with db.get_conn("chat") as conn:
        conn.execute("UPDATE attachments SET original_name = ? WHERE id = ?",
                     (safe, attachment_id))
    rec = get_attachment(attachment_id)
    if rec is None:
        fail(NOT_FOUND, "附件不存在")
    return rec


def touch_usage(attachment_id: str) -> None:
    """发送注入成功后的唯一记账点：use_count+1 / last_used_at=now（「最近用过」真源）。"""
    if not attachment_id:
        return
    with db.get_conn("chat") as conn:
        conn.execute(
            "UPDATE attachments SET use_count = use_count + 1, last_used_at = ? "
            "WHERE id = ?", (get_local_iso_timestamp(), attachment_id))


def clear_recent() -> int:
    """清空最近使用记录（只清计数与时间, 不删任何文件）。返回影响行数。"""
    with db.get_conn("chat") as conn:
        cur = conn.execute(
            "UPDATE attachments SET use_count = 0, last_used_at = NULL "
            "WHERE use_count > 0 OR last_used_at IS NOT NULL")
        return cur.rowcount or 0


def mark_extract_result(attachment_id: str, chars: int, ok: bool) -> None:
    """首次抽取后回填抽取态（S3）：供详情/文件页展示；不缓存正文。

    只在 status='none' 时写一次 —— 后续每轮抽取是纯函数，重复 UPDATE 无意义。
    best-effort: 状态回填不是数据路径, UPDATE 自身失败只记 WARNING,
      不向上抛 —— 否则一次状态写失败会把已成功的抽取折算成 attachment_failed。
    """
    if not attachment_id:
        return
    try:
        with db.get_conn("chat") as conn:
            conn.execute(
                "UPDATE attachments SET extract_status = ?, extract_chars = ? "
                "WHERE id = ? AND extract_status = 'none'",
                ("ok" if ok else "failed", max(0, int(chars)), attachment_id),
            )
    except Exception as e:  # noqa: BLE001 — best-effort 状态回填, 失败只留痕不阻断
        logger.warning("[attachments] 抽取态回填失败 id=%s err=%s", attachment_id, e)



def reextract(attachment_id: str) -> dict[str, Any] | None:
    """手动重跑真抽取: 重置抽取态后按契约文本出口重算并回填。

    仅 fallback_quality=content 的 kind(text/richdoc)有真抽取态可回填;
    卡/元数据类原样返回(无重试意义)。失败折算 extract_status='failed', 不抛异常。
    """
    att = get_attachment(attachment_id)
    if not att:
        return None
    from app.attachments.contract import KIND_CONTRACT  # 延迟导入防循环
    route = KIND_CONTRACT[("attachment", att.get("kind") or "binary")]
    if route.fallback_quality != "content":
        return att
    with db.get_conn("chat") as conn:
        conn.execute(
            "UPDATE attachments SET extract_status = 'none', extract_chars = 0 WHERE id = ?",
            (attachment_id,))
    try:
        text = extract.build_inject_text(att)
        mark_extract_result(attachment_id, len(text), True)
    except Exception as e:  # noqa: BLE001 — 重试失败折算 failed, 不向上抛
        logger.warning("[attachments] 重新抽取失败 id=%s err=%s", attachment_id, e)
        mark_extract_result(attachment_id, 0, False)
    return get_attachment(attachment_id)


def get_attachment(attachment_id: str) -> dict[str, Any] | None:
    """按 id 取单条(同步: resolver 在 to_thread 内调用)。"""
    if not attachment_id:
        return None
    with db.get_conn("chat") as conn:
        row = conn.execute(
            f"SELECT {_COLS} FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        d = _row_to_dict(row) if row else None
        if d:
            _decorate_global(conn, [d])
    return d


def get_attachment_scoped(attachment_id: str, session_id: str | None, *,
                          auto_promote: bool = False) -> dict[str, Any] | None:
    """按 id 取单条并校验访问权（会话归属校验 + global 全局放行）— 小欧-2026-11-07

    访问规则: scope='global' 对所有会话可读; session 级仍严格校验会话归属。
    auto_promote=True（跨会话引用/预览）时，非本会话的 session 级附件自动升级为全局后返回，
    用户不感知 404。session_id 为 None 时 fail-closed（拿不出凭据不给数据）。
    """
    att = get_attachment(attachment_id)
    if not att:
        return None
    if att.get("scope") == "global":
        return att
    if session_id and att.get("session_id") == session_id:
        return att
    if auto_promote and session_id:
        return promote_attachment(attachment_id)
    return None


def delete_attachment(attachment_id: str, session_id: str | None, *,
                      purge: bool = True, force: bool = False) -> None:
    """删记录（global 行对任意会话可删；session 行限本会话）。

    purge=True（默认）时按存储路径引用计数决定是否删磁盘文件：还有别的行指向同一路径
    就只删行，避免"删一条、其余全红"。被合集引用且未 force → 409 ATTACHMENT_IN_USE，
    确认后 force=True 一并清理素材包条目（条目身份=attachment_id，无 aid 旧条目按相对路径）。
    """
    att = get_attachment(attachment_id)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    if att.get("scope") != "global" and (not session_id or att.get("session_id") != session_id):
        fail(NOT_FOUND, "附件不存在")
    stored_path = att["stored_path"]
    # 2026-11-07 小欧: 合集条目身份=attachment_id; 无 aid 旧条目按写入时同源的
    #   rel_to_root 相对路径匹配(库存相对 path, 绝对 stored_path 永不相等) — 小欧-2026-11-07
    rel_path = rel_to_root(stored_path)
    with db.get_conn("chat") as conn:
        pack_refs = conn.execute(
            "SELECT COUNT(*) FROM material_pack_items WHERE attachment_id = ? "
            "OR (attachment_id IS NULL AND path = ?)",
            (attachment_id, rel_path),
        ).fetchone()[0]
        if pack_refs and not force:
            fail(ATTACHMENT_IN_USE, f"该文件仍被 {pack_refs} 个合集引用，确认后可一并删除")
        shared = conn.execute(
            "SELECT COUNT(*) FROM attachments WHERE stored_path = ? AND id <> ?",
            (stored_path, attachment_id),
        ).fetchone()[0]
        if purge and shared == 0:
            try:
                Path(stored_path).unlink(missing_ok=True)
            except OSError as e:
                logger.error(f"[attachments] purge 失败, 记录保留 id={attachment_id} err={e}")
                fail(ATTACHMENT_UNAVAILABLE, "附件磁盘删除失败，记录已保留")
        if purge:
            conn.execute(
                "DELETE FROM material_pack_items WHERE attachment_id = ? "
                "OR (attachment_id IS NULL AND path = ?)",
                (attachment_id, rel_path))
        conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))


def read_inject_text(attachment_id: str, session_id: str) -> str:
    """预览端点数据源: 与 resolver 同一条生成路径, 不产生第二套口径。

    访问权经 get_attachment_scoped 校验(会话归属 + global 放行)。预览是纯读: 不自动收藏
    (auto_promote=False), 跨会话 session 级附件预览如实 404 —— 跨会话自动升级只属于
    发送注入(resolver)与手动/引用链, 预览不产生任何写副作用。
    """
    att = get_attachment_scoped(attachment_id, session_id, auto_promote=False)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    try:
        return extract.build_inject_text(att)
    except Exception as e:  # noqa: BLE001 — S3改抛异常后预览兜底: 抽取失败降级说明文本不再HTTP 500, 与resolver失败折算同口径
        return f"[附件抽取失败({type(e).__name__})] 预览不可用。原文可通过下载查看; 发送引用时该附件按失败回执处理。"
