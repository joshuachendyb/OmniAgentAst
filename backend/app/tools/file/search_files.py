# -*- coding: utf-8 -*-
"""
F6: search_files — 搜索文件名

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

import asyncio
import fnmatch
import os
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS, DEFAULT_PAGE_SIZE
from app.constants import ERR_FILE_SEARCH_FAILED
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _match_fnmatch(name: str, pattern: str, ignore_case: bool) -> bool:
    """统一封装fnmatch — 小健 2026-05-25 — 小欧 2026-06-22"""
    if ignore_case:
        return fnmatch.fnmatch(name.lower(), pattern.lower())
    return fnmatch.fnmatch(name, pattern)


def _is_already_seen_or_skipped(name: str, seen: set, seen_count: int, start: int) -> Tuple[bool, bool]:
    """去重和跳过逻辑 — 小欧 2026-06-22"""
    if name in seen:
        return True, False
    if seen_count < start:
        return False, True
    return False, False


def _collect_entry_result(relative_path: str, name: str, fpath: Path,
                           all_matches: List, llm_preview: List) -> None:
    """收集搜索结果条目 — 小欧 2026-06-22"""
    is_dir = fpath.is_dir()
    entry = {
        "name": name,
        "path": str(fpath.absolute()),
        "relative_path": relative_path,
        "type": "directory" if is_dir else "file",
    }
    if not is_dir:
        try:
            entry["size"] = fpath.stat().st_size
        except OSError:
            entry["size"] = 0
    all_matches.append(entry)
    if len(llm_preview) < 20:
        llm_preview.append(f"{relative_path}")


def _build_search_files_llm_data(
    exec_code: str, duration_ms: int,
    search_dir: str = "", total: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """search_files的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"搜索文件失败: {detail}",
            "action": {"tool": "search_files", "tool_zh": "搜索文件", "target": search_dir, "params": {}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_SEARCH_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"搜索完成: {total}个匹配",
        "action": {"tool": "search_files", "tool_zh": "搜索文件", "target": search_dir, "params": {}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "total": {"value": total, "text": f"{total}个匹配"},
        },
    }


async def search_files(
    pattern: str,
    search_dir: str,
    recursive: bool = True,
    ignore_case: bool = True,
    type: Optional[Literal["file", "directory"]] = None,
) -> Dict[str, Any]:
    """搜索文件名 — 小沈 2026-05-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    max_depth = 50
    is_valid, error_msg = _validate_path(search_dir)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=error_msg)
        return build_error(data={"error_detail": error_msg, "params": {"search_dir": search_dir}}, llm_data=llm_data)
    if not pattern or not pattern.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail="文件名匹配模式不能为空")
        return build_error(data={"error_detail": "文件名匹配模式不能为空", "params": {"pattern": pattern}}, llm_data=llm_data)
    path = Path(os.path.expanduser(search_dir))
    if not path.exists():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"搜索目录不存在: {search_dir}")
        return build_error(data={"error_detail": "搜索目录不存在", "params": {"search_dir": search_dir}}, llm_data=llm_data)

    deadline = time.monotonic() + TOOL_TIMEOUTS.get("search_files", TOOL_TIMEOUTS["default"]) - 2
    all_matches: List = []
    llm_preview: List = []
    seen_files: set = set()
    start_offset = 0

    def _search_sync():
        nonlocal seen_files
        for root, dirs, files in os.walk(path):
            if time.monotonic() > deadline:
                logger.warning(f"[search_files] 超时自检触发,提前返回{len(all_matches)}个匹配")
                break
            if not recursive:
                dirs.clear()
            elif max_depth:
                depth = root[len(str(path)):].count(os.sep)
                if depth >= max_depth:
                    dirs.clear()
            if type != "file":
                for d in dirs:
                    if not _match_fnmatch(d, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, d), path)
                    dup, skip = _is_already_seen_or_skipped(relative, seen_files, len(all_matches), start_offset)
                    if dup or skip:
                        continue
                    _collect_entry_result(relative, d, Path(os.path.join(root, d)), all_matches, llm_preview)
            if type != "directory":
                for f in files:
                    if not _match_fnmatch(f, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, f), path)
                    dup, skip = _is_already_seen_or_skipped(relative, seen_files, len(all_matches), start_offset)
                    if dup or skip:
                        continue
                    _collect_entry_result(relative, f, Path(os.path.join(root, f)), all_matches, llm_preview)

    try:
        await asyncio.to_thread(_search_sync)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"搜索失败: {e}")
        return build_error(data={"error_detail": str(e), "params": {"search_dir": search_dir}}, llm_data=llm_data)

    all_matches.sort(key=lambda x: x.get("name", ""))
    total = len(all_matches)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    llm_data = _build_search_files_llm_data("success", duration_ms, search_dir=search_dir, total=total)
    return build_success(
        data={"matches": all_matches, "total": total, "search_dir": search_dir, "pattern": pattern},
        llm_data=llm_data,
    )