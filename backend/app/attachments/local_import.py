# 编辑历史:
# 2026-11-04 Agnes - 新建: 同机本地导入(仅同机可用, 复用 save_bytes) — Agnes-2026-11-04
# 2026-11-05 小欧 - 安全修正: XFF 仅在受信代理后采信且取最右一跳(旧版无条件信最左可伪造);
#   路径强制绝对盘符/拒 UNC/拒符号链接, resolve 后限定可读根集合; 先 stat 判大小再读盘(旧版先读后判易 OOM);
#   拒绝非普通文件 — 小欧-2026-11-05
# 2026-11-06 小欧 - 改名 local.py→local_import.py: 文件名点明"同机本地导入"职责(原名 local 过于宽泛),
#   与 *_service.py 等"文件名=职责"惯例对齐; 模块内函数不变 — 小欧-2026-11-06
"""同机本地导入 —— 附件「进系统」第二通道（仅同机）。

纯浏览器拿不到本地路径，但同机下后端可访问本地文件系统。
「不传文件」= 后端读盘导入，而非前端拿路径。
落盘仍由 save_bytes 在 attachments/ 生成（路径是读源非落盘目标）。

安全边界：
  1. 同机判定只认真实客户端 IP；X-Forwarded-For 仅在直连对端是受信代理时采信，且取最右一跳
     （最左由客户端自填，可伪造）。受信代理列表默认空 = 不采信任何 XFF。
  2. 导入路径必须绝对盘符路径，拒绝 UNC / 相对路径 / 符号链接 / 非普通文件。
  3. resolve 后必须落在可读根集合（项目根 / 用户主目录 / 会话工作区）内。
  4. 先 stat 判大小再读盘，读入字节复核一次（防 stat 与 read 之间被替换）。
"""
import os
import socket
from pathlib import Path

from fastapi import Request

from app.attachments import attachment_service as service
from app.attachments import extract
from app.config import get_config
from app.db import db
from app.file_browse.errors import (
    ATTACHMENT_TOO_LARGE,
    LOCAL_IMPORT_DISABLED,
    NOT_FOUND,
    UNSUPPORTED_TYPE,
    fail,
)

# 受信代理白名单（逗号分隔 IP，默认空=不采信任何 X-Forwarded-For）。
# 仅当直连对端命中本列表时才解析 XFF；否则一律用 request.client.host。
_TRUSTED_PROXIES: set[str] = {
    ip.strip() for ip in os.environ.get("ATTACHMENTS_TRUSTED_PROXIES", "").split(",") if ip.strip()
}


def _local_ips() -> set[str]:
    """本机 IP 集合：回环 + 所有网卡 IPv4。"""
    ips = {"127.0.0.1", "::1", "localhost"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return ips


def _client_ip(request: Request) -> str:
    """真实客户端 IP：仅在受信代理后采信 XFF，且取最右一跳。

    最左一跳由客户端自填（可伪造 `X-Forwarded-For: 127.0.0.1` 冒充同机），
    最右一跳是受信代理追加、离服务端最近的可信值。
    """
    peer = request.client.host if request.client else ""
    if peer in _TRUSTED_PROXIES:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[-1].strip()
    return peer


def is_local_request(request: Request) -> bool:
    """真实客户端 IP 是否本机（同机判断，不信任前端、不信任可伪造的 XFF）。"""
    return _client_ip(request) in _local_ips()


def _import_roots(session_id: str) -> set[Path]:
    """可导入根集合：项目根 + 用户主目录 + 会话工作区。"""
    roots: set[Path] = set()
    try:
        roots.add(Path(get_config().get_project_root()).resolve())
    except Exception:  # noqa: BLE001 — 取不到项目根不阻断其余根
        pass
    try:
        roots.add(Path.home().resolve())
    except Exception:  # noqa: BLE001
        pass
    with db.get_conn("chat") as conn:
        for row in conn.execute(
            "SELECT path FROM chat_session_workspaces WHERE session_id = ?",
            (session_id,),
        ).fetchall():
            raw = row["path"] if hasattr(row, "keys") else row[0]
            if raw:
                roots.add(Path(raw).resolve())
    return roots


def _resolve_import_path(session_id: str, raw: str) -> Path:
    """校验并解析导入路径；任何越界/非法一律 fail()，绝不返回半成品。"""
    text = (raw or "").strip()
    if not text:
        fail(NOT_FOUND, "缺少文件路径")
    if text.startswith(("\\\\", "\\", "/")) or not Path(text).is_absolute():
        fail(UNSUPPORTED_TYPE, "仅支持绝对盘符路径（如 D:\\资料\\a.pdf）")
    p = Path(text)
    if p.is_symlink():
        fail(UNSUPPORTED_TYPE, "不支持符号链接")
    if not p.exists():
        fail(NOT_FOUND, "文件不存在")
    if not p.is_file():
        fail(UNSUPPORTED_TYPE, "不是文件")
    target = p.resolve()
    for root in _import_roots(session_id):
        try:
            target.relative_to(root)
            return target
        except ValueError:
            continue
    fail(UNSUPPORTED_TYPE, "仅支持从项目根、用户目录或会话工作区导入")


def import_local(session_id: str, path: str, *, request: Request) -> dict:
    """同机本地导入：同机判定 → 路径校验 → stat 判限 → 读盘 → 复用 save_bytes（DRY）。

    安全：仅同机（LOCAL_IMPORT_DISABLED, 403）；先在 stat 阶段拒绝超限文件，
    避免先读入内存再判大小导致 OOM；读入后由 save_bytes 统一复核大小/白名单/去重/配额。
    """
    if not is_local_request(request):
        fail(LOCAL_IMPORT_DISABLED, "本地导入仅同机可用")
    target = _resolve_import_path(session_id, path)
    limit = (service.MAX_IMAGE_BYTES
             if target.suffix.lower() in extract.IMAGE_SUFFIXES
             else service.MAX_FILE_BYTES)
    if target.stat().st_size > limit:
        fail(ATTACHMENT_TOO_LARGE)
    data = target.read_bytes()
    if len(data) > limit:            # stat 与 read 之间文件可能被替换
        fail(ATTACHMENT_TOO_LARGE)
    return service.save_bytes(session_id, target.name, data, source_path=str(target))
