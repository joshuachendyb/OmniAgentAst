# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 - 小欧 - 新建: 运行代码指纹(frozen/app_root/关键模块哈希), 落盘 + /health 暴露
"""build_fingerprint — 运行代码指纹 — 小欧 2026-11-15

【问题】app/ 以源码树放入 _internal/app, 改 py 只需重启生效; 但只要出现
"改了磁盘没重启" 或 "copy2 覆盖后 mtime 更旧", 任何一方都无法自证跑的是哪份代码,
2026-11-15 pid 412 事故的排查成本全部来自这一点(mtime 完全不可用作证据)。

【做法】启动时对关键模块算 sha256(前 16 位)并记录 frozen/_MEIPASS/pid/exe 大小,
落一条 INFO 日志, 同时经 /health.build 暴露。dev、打包、部署目录三处比对同一组哈希,
不一致即可判定"运行的不是你以为的那份代码"。
"""
import hashlib
import os
import sys
import time
from pathlib import Path

from app.logger import logger

_KEY_MODULES = (
    "tools/fundamental/execute_shell_command.py",
    "tools/fundamental/shell_background.py",
    "utils/spawn_gate.py",
    "utils/proc_io.py",
    "utils/console_mode.py",
)

_snapshot = None


def app_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _file_sha16(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _exe_info():
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable)
    st = exe.stat()
    return {"path": str(exe), "size": st.st_size, "mtime": int(st.st_mtime)}


def build_snapshot(force: bool = False) -> dict:
    """关键模块指纹(进程内缓存; 强制刷新只在部署校验脚本里用) — 小欧 2026-11-15"""
    global _snapshot
    if _snapshot is not None and not force:
        return _snapshot
    root = app_root()
    modules = {}
    for rel in _KEY_MODULES:
        path = root / rel
        modules[rel] = (
            {"sha256": _file_sha16(path), "size": path.stat().st_size,
             "mtime": int(path.stat().st_mtime)}
            if path.is_file() else {"missing": True}
        )
    _snapshot = {
        "frozen": bool(getattr(sys, "frozen", False)),
        "app_root": str(root),
        "meipass": getattr(sys, "_MEIPASS", ""),
        "exe": _exe_info(),
        "pid": os.getpid(),
        "detected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modules": modules,
    }
    return _snapshot


def log_build_fingerprint() -> None:
    """启动期落一条完整指纹: 部署核对的第一证据 — 小欧 2026-11-15"""
    snap = build_snapshot(force=True)
    parts = [f"{k}={v.get('sha256', 'MISSING')}" for k, v in snap["modules"].items()]
    logger.info(
        f"[构建指纹] frozen={snap['frozen']} app_root={snap['app_root']} "
        f"meipass={snap['meipass']} pid={snap['pid']} exe={snap['exe']}")
    logger.info("[构建指纹] " + " ".join(parts))
