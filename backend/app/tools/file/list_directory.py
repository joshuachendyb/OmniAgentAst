# -*- coding: utf-8 -*-
"""
F5: list_directory — 列出目录内容

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import asyncio
import time as _time_mod
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_FILE_LIST_DIR_FAILED
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _classify_size(size: int) -> str:
    """文件大小分桶 — 小健 2026-05-25 — 小欧 2026-06-22"""
    if size < 1024: return "<1KB"
    if size < 10240: return "1KB-10KB"
    if size < 102400: return "10KB-100KB"
    if size < 1048576: return "100KB-1MB"
    return ">1MB"


def _build_entry(item: Path, st: os.stat_result) -> Dict[str, Any]:
    """构建单个目录条目 — 小健 2026-05-25 — 小欧 2026-06-22"""
    is_dir = item.is_dir()
    return {
        "name": item.name,
        "path": str(item.absolute()),
        "type": "directory" if is_dir else "file",
        "size": None if is_dir else st.st_size,
        "mtime": st.st_mtime,
    }


def _scan_directory_sync(
    path: Path, recursive: bool, max_depth: int,
    include_hidden: bool, deadline: float,
) -> Tuple[List[Dict], Dict, Dict, Dict]:
    """同步扫描目录 — 小健 2026-05-25 — 小欧 2026-06-22"""
    entries = []
    stats = {"total_size": 0, "dir_count": 0, "file_count": 0}
    ext_counter: Dict[str, int] = {}
    size_bins = {"<1KB": 0, "1KB-10KB": 0, "10KB-100KB": 0, "100KB-1MB": 0, ">1MB": 0}
    _timed_out = False

    def _scan_recursive(current_path: Path, current_depth: int):
        nonlocal _timed_out
        if current_depth > max_depth:
            return
        if time.monotonic() > deadline:
            _timed_out = True
            return
        try:
            for item in current_path.iterdir():
                if _timed_out:
                    return
                try:
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    st = item.stat()
                    entry = _build_entry(item, st)
                    entries.append(entry)
                    if item.is_dir():
                        stats["dir_count"] += 1
                        _scan_recursive(item, current_depth + 1)
                        if _timed_out:
                            return
                    else:
                        stats["total_size"] += st.st_size
                        stats["file_count"] += 1
                        ext = item.suffix.lower().lstrip('.') if item.suffix else ''
                        ext_counter[ext] = ext_counter.get(ext, 0) + 1
                        size_bins[_classify_size(st.st_size)] += 1
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            return

    if recursive:
        _scan_recursive(path, 1)
    else:
        for item in path.iterdir():
            try:
                if not include_hidden and item.name.startswith('.'):
                    continue
                st = item.stat()
                entry = _build_entry(item, st)
                entries.append(entry)
                if item.is_dir():
                    stats["dir_count"] += 1
                else:
                    stats["total_size"] += st.st_size
                    stats["file_count"] += 1
                    ext = item.suffix.lower().lstrip('.') if item.suffix else ''
                    ext_counter[ext] = ext_counter.get(ext, 0) + 1
                    size_bins[_classify_size(st.st_size)] += 1
            except (PermissionError, OSError):
                continue

    return entries, stats, ext_counter, size_bins


def _count_tree_stats(node: dict) -> Tuple[int, int, int]:
    """递归统计树形结构的文件数/目录数/总大小 — 小健 2026-05-25 — 小欧 2026-06-22"""
    files = dirs = total_size = 0
    if node.get("type") == "file":
        files = 1
        total_size = node.get("size", 0)
    elif node.get("type") == "directory":
        dirs = 1
    for child in node.get("children", []):
        cf, cd, cs = _count_tree_stats(child)
        files += cf; dirs += cd; total_size += cs
    return files, dirs, total_size


def _build_list_success(entries: List, total: int, path: Path,
                         statistics: Dict, start_offset: int,
                         max_display: int) -> Dict[str, Any]:
    """构建list模式的原始数据 — 小健 2026-05-25 — 小欧 2026-06-22"""
    truncated = total > max_display
    display_entries = entries[start_offset:start_offset + max_display]
    return {
        "entries": display_entries,
        "total": total,
        "statistics": statistics,
        "truncated": truncated,
    }


def _build_list_directory_llm_data(
    exec_code: str, duration_ms: int,
    dir_path: str = "", total: int = 0,
    truncated: bool = False, detail: str = "",
) -> Dict[str, Any]:
    """list_directory的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"列出目录失败: {detail}",
            "action": {"tool": "list_directory", "tool_zh": "列出目录", "target": dir_path, "params": {}},
            "status": {"exec_code": "error", "message": "列出目录失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    m: Dict[str, Any] = {"total": {"value": total, "text": f"{total}项"}}
    if truncated:
        m["truncated"] = {"value": True, "text": "已截断"}
    return {
        "summary": f"列出目录成功: {dir_path} ({total}项)",
        "action": {"tool": "list_directory", "tool_zh": "列出目录", "target": dir_path, "params": {}},
        "status": {"exec_code": "success", "message": "列出目录成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": m,
    }


async def _get_directory_tree(
    dir_path: str, max_depth: int = 10,
) -> Dict[str, Any]:
    """获取目录树原始数据 — 小欧 2026-06-22"""
    t0 = _time_mod.perf_counter()
    is_valid, error_msg = _validate_path(dir_path)
    if not is_valid:
        return {"error_detail": error_msg, "params": {"dir_path": dir_path}}

    path = Path(dir_path)
    if not path.exists():
        return {"error_detail": "目录不存在", "params": {"dir_path": dir_path}}
    if not path.is_dir():
        return {"error_detail": "不是目录", "params": {"dir_path": dir_path}}

    def _build_tree(current_path: Path, depth: int = 0) -> Optional[Dict[str, Any]]:
        if depth > max_depth:
            return None
        try:
            st = current_path.stat()
        except OSError:
            return None
        node: Dict[str, Any] = {
            "name": current_path.name,
            "path": str(current_path.absolute()),
            "type": "directory" if current_path.is_dir() else "file",
            "size": st.st_size if not current_path.is_dir() else None,
            "mtime": st.st_mtime,
        }
        if current_path.is_dir():
            children = []
            try:
                for item in sorted(current_path.iterdir(), key=lambda x: x.name.lower()):
                    child = _build_tree(item, depth + 1)
                    if child:
                        children.append(child)
            except (PermissionError, OSError):
                pass
            node["children"] = children
        return node

    tree = await asyncio.to_thread(_build_tree, path)
    if tree is None:
        return {"error_detail": "构建目录树失败", "params": {"dir_path": dir_path}}

    f, d, s = _count_tree_stats(tree)
    return {"tree": tree, "statistics": {"file_count": f, "dir_count": d, "total_size": s}}


async def list_directory(
    dir_path: str,
    recursive: bool = False,
    sort_by: str = "name",
    include_hidden: bool = False,
) -> Dict[str, Any]:
    """列出目录内容 — 小沈 2026-05-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    max_depth = 10
    format_mode = "tree" if recursive else "list"

    if sort_by not in ("name", "size", "mtime"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name'/'size'/'mtime',当前值: '{sort_by}'")
        return build_error(data={"error_detail": f"sort_by只支持name/size/mtime", "params": {"sort_by": sort_by}}, llm_data=llm_data)

    if format_mode == "tree":
        tree_result = await _get_directory_tree(dir_path=dir_path, max_depth=max_depth)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if "error_detail" in tree_result:
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=tree_result["error_detail"])
            return build_error(data=tree_result, llm_data=llm_data)
        else:
            llm_data = _build_list_directory_llm_data("success", duration_ms, dir_path=dir_path, total=tree_result["statistics"]["file_count"] + tree_result["statistics"]["dir_count"])
            return build_success(data=tree_result, llm_data=llm_data)

    is_valid, error_msg = _validate_path(dir_path)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=error_msg)
        return build_error(data={"error_detail": error_msg, "params": {"dir_path": dir_path}}, llm_data=llm_data)

    path = Path(dir_path)
    start_offset = 0

    try:
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"目录不存在: {dir_path}")
            return build_error(data={"error_detail": "目录不存在", "params": {"dir_path": dir_path}}, llm_data=llm_data)
        if not path.is_dir():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"不是目录: {dir_path}")
            return build_error(data={"error_detail": "不是目录", "params": {"dir_path": dir_path}}, llm_data=llm_data)

        deadline = time.monotonic() + TOOL_TIMEOUTS.get("list_directory", TOOL_TIMEOUTS["default"]) - 2
        all_entries, stats, file_types, size_distribution = await asyncio.to_thread(
            _scan_directory_sync, path, recursive, max_depth, include_hidden, deadline,
        )

        if sort_by == "size":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("size") or 0), reverse=True)
        elif sort_by == "mtime":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("mtime", 0)), reverse=True)
        else:
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

        total = len(all_entries)
        MAX_DISPLAY_ENTRIES = 200
        statistics = {
            "total_size": stats["total_size"], "dir_count": stats["dir_count"],
            "file_count": stats["file_count"], "sort_by": sort_by,
            "file_types": file_types, "size_distribution": size_distribution,
        }

        if total > MAX_DISPLAY_ENTRIES:
            logger.warning(f"[list_directory] Large directory truncated: path={path}, total={total}")

        list_data = _build_list_success(all_entries, total, path, statistics, start_offset, MAX_DISPLAY_ENTRIES)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("success", duration_ms, dir_path=dir_path, total=total, truncated=list_data["truncated"])
        return build_success(data=list_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to list directory {dir_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"dir_path": dir_path}}, llm_data=llm_data)