# 编辑历史:
# 2026-11-07 小欧 - 新建: 同机文件系统入口(磁盘列表 + 授权目录台账), 供「我的电脑」自研浏览器使用;
#   授权目录落 SQLite(local_auth_dirs) 而非 config.yaml —— 避免新增配置键的三处同步(example/registry/运行时),
#   且授权/撤销是运行时数据而非配置 — 小欧-2026-11-07
# 2026-11-07 小欧 - 增 quick_paths: 桌面/下载/文档 常用位置(只列真实存在的), 随 /fs/drives 下发,
#   避免前端自拼用户目录(中文系统物理目录名仍为英文) — 小欧-2026-11-07
"""同机文件系统入口 —— 磁盘列表与「用户授权目录」台账。

为什么需要：
  同机导入(local_import)原本只允许项目根 + 会话工作区(安全修正)，用户无法导入
  桌面/下载/资料盘里的文件。放开全盘等于把 `.ssh` 等敏感目录一起交给模型，
  故引入**目录粒度授权**：用户首次从某目录导入时确认一次，写入台账，可随时撤销。

安全边界：
  1. 仅同机可用（判定复用 local_import.is_local_request，唯一口径）。
  2. 只接受盘符绝对路径；拒 UNC / 相对 / 符号链接 / 非目录。
  3. 硬黑名单目录（凭据/系统配置/浏览器配置）永不进台账。
  4. 每次授权 / 撤销 / 列盘写审计日志（路径 + 时间）。
"""
import ctypes
import os
import shutil
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db import db
from app.file_browse.errors import INVALID_PARAM, fail
from app.logger import logger

# 硬黑名单：目录名（任一层命中即拒）
_SENSITIVE_NAMES = {
    ".ssh", ".aws", ".gnupg", ".kube", ".docker", ".git-credentials",
    "ntuser.dat", "credentials", "protect",
}
# 硬黑名单：路径片段（小写比较）
_SENSITIVE_PARTS = (
    "\\system32\\config",
    "\\google\\chrome\\user data",
    "\\mozilla\\firefox",
    "\\microsoft\\credentials",
    "\\microsoft\\protect",
)


def is_sensitive(path: Path) -> bool:
    """路径是否落在硬黑名单内（凭据 / 系统配置 / 浏览器配置）。"""
    text = str(path).lower()
    if any(part in text for part in _SENSITIVE_PARTS):
        return True
    return any(p.lower() in _SENSITIVE_NAMES for p in path.parts)


def _volume_label(root: str) -> str:
    """卷标（Windows）；非 Windows 或读取失败返回空串。"""
    if os.name != "nt":
        return ""
    try:
        buf = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(root), buf, len(buf), None, None, None, None, 0
        )
        return buf.value if ok else ""
    except (AttributeError, OSError):
        return ""


def _drive_roots() -> List[str]:
    """本机盘符根（`C:\\` 形式）。os.listdrives 仅 Windows/3.12+，退化按字母探测。"""
    listdrives = getattr(os, "listdrives", None)
    if listdrives is not None:
        try:
            return [d for d in listdrives() if d]
        except OSError:
            pass
    return [f"{c}:\\" for c in string.ascii_uppercase if Path(f"{c}:\\").exists()]


def list_drives() -> List[Dict[str, Any]]:
    """磁盘列表：盘符 + 卷标 + 总/剩余空间。不可读的盘照列（ready=False）。"""
    drives: List[Dict[str, Any]] = []
    for root in _drive_roots():
        item: Dict[str, Any] = {
            "path": root,
            "label": _volume_label(root),
            "total": 0,
            "free": 0,
            "ready": False,
        }
        try:
            usage = shutil.disk_usage(root)
            item.update(total=usage.total, free=usage.free, ready=True)
        except OSError:
            pass
        drives.append(item)
    return drives


def quick_paths() -> List[Dict[str, str]]:
    """常用位置（桌面/下载/文档）：只列真实存在的目录，供抽屉快捷入口。"""
    home = Path.home()
    names = (("桌面", "Desktop"), ("下载", "Downloads"), ("文档", "Documents"))
    return [
        {"label": label, "path": str(home / name)}
        for label, name in names
        if (home / name).is_dir()
    ]


def _row_value(row: Any, key: str, index: int) -> Any:
    """行取值兼容（sqlite3.Row 与裸元组）。"""
    return row[key] if hasattr(row, "keys") else row[index]


def list_authorized() -> List[Dict[str, Any]]:
    """已授权目录台账（按授权时间升序）。"""
    with db.get_conn("chat") as conn:
        rows = conn.execute(
            "SELECT path, created_at FROM local_auth_dirs ORDER BY created_at"
        ).fetchall()
    return [
        {"path": _row_value(r, "path", 0), "created_at": _row_value(r, "created_at", 1)}
        for r in rows
    ]


def authorized_roots() -> set[Path]:
    """已授权目录的可读根集合（供 local_import 并入可导入根）。"""
    roots: set[Path] = set()
    for item in list_authorized():
        try:
            roots.add(Path(item["path"]).resolve())
        except OSError:
            continue
    return roots


def _validate_dir(raw: str) -> Path:
    """校验授权路径：盘符绝对路径 + 真实存在的目录 + 非链接 + 非黑名单。"""
    text = (raw or "").strip()
    if not text:
        fail(INVALID_PARAM, "缺少目录路径")
    if text.startswith(("\\\\", "/")) or not Path(text).is_absolute():
        fail(INVALID_PARAM, "仅支持绝对盘符路径（如 D:\\资料）")
    p = Path(text)
    if p.is_symlink():
        fail(INVALID_PARAM, "不支持符号链接目录")
    if not p.exists():
        fail(INVALID_PARAM, "目录不存在")
    if not p.is_dir():
        fail(INVALID_PARAM, "该路径不是目录")
    target = p.resolve()
    if is_sensitive(target):
        fail(INVALID_PARAM, "该目录属于受保护区域，禁止授权")
    return target


def authorize(raw: str) -> List[Dict[str, Any]]:
    """授权一个目录（幂等）；返回最新台账。"""
    target = _validate_dir(raw)
    now = datetime.now().isoformat(timespec="seconds")
    with db.get_conn("chat") as conn:
        conn.execute(
            "INSERT OR IGNORE INTO local_auth_dirs(path, created_at) VALUES (?, ?)",
            (str(target), now),
        )
    logger.info(f"[local_fs] authorize dir={target} at={now}")
    return list_authorized()


def revoke(raw: str) -> List[Dict[str, Any]]:
    """撤销授权（不影响已导入的附件）；返回最新台账。"""
    text = (raw or "").strip()
    if not text:
        fail(INVALID_PARAM, "缺少目录路径")
    try:
        target = str(Path(text).resolve())
    except OSError:
        target = text
    with db.get_conn("chat") as conn:
        conn.execute("DELETE FROM local_auth_dirs WHERE path = ?", (target,))
    logger.info(f"[local_fs] revoke dir={target}")
    return list_authorized()


def is_authorized(path: Path) -> bool:
    """该路径是否落在任一已授权目录内。"""
    target = path.resolve()
    for root in authorized_roots():
        if target == root or root in target.parents:
            return True
    return False


def host_label() -> Optional[str]:
    """主机名（抽屉标题「我的电脑 · {host}」用）。"""
    try:
        return os.environ.get("COMPUTERNAME") or os.uname().nodename  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None
