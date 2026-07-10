# -*- coding: utf-8 -*-
"""
file_state — 文件状态追踪，取代 edit_text_file 的本地 mtime 缓存

职责: 记录文件读取/写入时的 mtime+content_hash，提供冲突检测和无操作跳过
小欧 2026-07-05
"""
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.logger import logger

# {resolved_path_str: (mtime_ns, content_hash)}
_state: Dict[str, Tuple[int, str]] = {}


def _resolve(file_path: str) -> str:
    return str(Path(file_path).resolve())


def record_read(file_path: str, content: str) -> None:
    """记录读取状态：mtime + content_hash — 小欧 2026-07-05 — 小沈 2026-07-05 修复_resolve重复调用"""
    resolved = Path(file_path).resolve()
    key = str(resolved)
    try:
        mtime = resolved.stat().st_mtime_ns
    except OSError:
        mtime = 0
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    _state[key] = (mtime, h)


def record_write(file_path: str) -> None:
    """写入后更新 mtime，使下次 check_conflict 不误报 — 小欧 2026-07-05 — 小沈 2026-07-05 修复_resolve重复调用"""
    resolved = Path(file_path).resolve()
    key = str(resolved)
    try:
        mtime = resolved.stat().st_mtime_ns
    except OSError:
        mtime = 0
    if key in _state:
        old_mtime, old_hash = _state[key]
        _state[key] = (mtime, old_hash)
    else:
        _state[key] = (mtime, "")


def check_conflict(file_path: str) -> Optional[str]:
    """检查文件自上次 record_read/record_write 后是否被外部修改
    返回 None=无冲突, str=警告信息 — 小欧 2026-07-05 — 小沈 2026-07-05 修复_resolve重复调用"""
    resolved = Path(file_path).resolve()
    key = str(resolved)
    recorded = _state.get(key)
    if recorded is None:
        return None
    recorded_mtime, _ = recorded
    try:
        current = resolved.stat().st_mtime_ns
    except OSError:
        return None
    if current != recorded_mtime:
        return (
            f"文件 {file_path} 自上次读取后被外部修改，"
            "当前操作可能覆盖外部变更。建议先 readtext 确认最新内容"
        )
    return None


def is_unchanged(file_path: str, content: str) -> bool:
    """检测内容是否与上次读取一致（无操作跳过）— 小欧 2026-07-05 — 小沈 2026-07-05 修复_resolve重复调用"""
    key = str(Path(file_path).resolve())
    recorded = _state.get(key)
    if recorded is None:
        return False
    _, recorded_hash = recorded
    if not recorded_hash:
        return False
    return hashlib.md5(content.encode("utf-8")).hexdigest() == recorded_hash


def check_conflict_strict(file_path: str) -> Optional[str]:
    """严格冲突检查（阻断级）：与 check_conflict 同逻辑但语义为阻断 — 小欧 2026-07-05"""
    resolved = Path(file_path).resolve()
    key = str(resolved)
    recorded = _state.get(key)
    if recorded is None:
        return None
    recorded_mtime, _ = recorded
    try:
        current = resolved.stat().st_mtime_ns
    except OSError:
        return None
    if current != recorded_mtime:
        return (
            f"文件 {file_path} 自上次读取后被外部修改，"
            "请先 readtext 确认最新内容后再操作"
        )
    return None


def clear_state(file_path: str) -> None:
    """删除后清除状态 — 小欧 2026-07-05 — 小沈 2026-07-05 修复_resolve重复调用"""
    key = str(Path(file_path).resolve())
    _state.pop(key, None)
