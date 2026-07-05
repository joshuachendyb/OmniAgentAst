# -*- coding: utf-8 -*-
"""
F5: list_directory — 列出目录内容

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import asyncio
import time as _time_mod
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import ERR_FILE_LIST_DIR_FAILED
from app.tools.tool_constants import TOOL_TIMEOUTS, LISTDIR_PAGE_SIZE
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger


# 文件系统遍历时跳过噪声目录 — 小欧 2026-07-05
_SKIP_DIRS = frozenset({
    '__pycache__', 'node_modules', 'bower_components',
    '.git', '.svn', '.hg',
    '.next', '.nuxt', 'dist', 'build', 'target', 'out',
    '.venv', 'venv', '.env', 'env',
    '.idea', '.vscode', '.yarn', '.pnp', 'coverage',
    '.terraform', '.serverless', 'vendor',
})


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
        if _time_mod.monotonic() > deadline:
            _timed_out = True
            return
        try:
            for item in current_path.iterdir():
                if _timed_out:
                    return
                try:
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    if item.name in _SKIP_DIRS:
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
                if item.name in _SKIP_DIRS:
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
    hint: str = "",
) -> Dict[str, Any]:
    """list_directory的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数+action params补齐+warning detail动态化+去死代码"""
    if exec_code == "error":
        error_msg = detail if detail else "列出目录失败"
        return {
            "summary": f"列出目录失败: {detail}",
            "action": {"tool": "listdir", "tool_zh": "列出目录", "target": dir_path, "params": {"dir_path": dir_path}},
            "status": {"exec_code": "error", "message": error_msg, "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": hint if hint else "请检查目录路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    m: Dict[str, Any] = {"total": {"value": total, "text": f"{total}项"}}
    if exec_code == "warning":
        m["truncated"] = {"value": True, "text": "已截断"}
        warning_detail = detail if detail else "结果过多已截断，仅显示前200项"
        warning_hint = hint if hint else "请使用更精确的路径或筛选条件"
        return {
            "summary": f"列出目录成功: {dir_path} ({total}项，已截断)",
            "action": {"tool": "listdir", "tool_zh": "列出目录", "target": dir_path, "params": {"dir_path": dir_path}},
            "status": {"exec_code": "warning", "message": "目录内容不完整", "code": "", "detail": warning_detail, "hint": warning_hint},
            "duration_ms": duration_ms,
            "metrics": m,
        }
    return {
        "summary": f"列出目录成功: {dir_path} ({total}项)",
        "action": {"tool": "listdir", "tool_zh": "列出目录", "target": dir_path, "params": {"dir_path": dir_path}},
        "status": {"exec_code": "success", "message": "列出目录成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": m,
    }


async def listdir(
    dir_path: str,
    sort_by: str = "name",
    include_hidden: bool = False,
    offset: int = 0,
) -> Dict[str, Any]:
    """列出目录内容 — 小沈 2026-05-19 — 小欧 2026-06-22 — 小沈 2026-07-03 拆分tree — 小欧 2026-07-04 offset分页"""
    t0 = _time_mod.perf_counter()

    if not dir_path or not dir_path.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail="dir_path不能为空", hint="请提供有效的目录路径")
        return build_error(data={"error_detail": "dir_path不能为空", "params": {"dir_path": dir_path}}, llm_data=llm_data)

    if sort_by not in ("name", "size", "mtime"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name'/'size'/'mtime',当前值: '{sort_by}'", hint="sort_by参数只能为name/size/mtime")
        return build_error(data={"error_detail": f"sort_by只支持name/size/mtime", "params": {"sort_by": sort_by}}, llm_data=llm_data)

    if offset < 0:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"offset必须>=0,当前值: {offset}", hint="offset从0开始,负值无效")
        return build_error(data={"error_detail": f"offset必须>=0", "params": {"offset": offset}}, llm_data=llm_data)

    path = Path(dir_path)
    start_offset = offset

    try:
        # 工具层校验：非空/保留字符/保留名/系统目录/路径存在+是目录 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.LIST_DIR, dir_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=err)
            return build_error(data={"error_detail": err, "params": {"dir_path": dir_path}}, llm_data=llm_data)

        deadline = _time_mod.monotonic() + TOOL_TIMEOUTS.get("listdir", TOOL_TIMEOUTS["default"]) - 2
        all_entries, stats, file_types, size_distribution = await asyncio.to_thread(
            _scan_directory_sync, path, False, 10, include_hidden, deadline,
        )

        if sort_by == "size":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("size") or 0), reverse=True)
        elif sort_by == "mtime":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("mtime", 0)), reverse=True)
        else:
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

        total = len(all_entries)
        statistics = {
            "total_size": stats["total_size"], "dir_count": stats["dir_count"],
            "file_count": stats["file_count"], "sort_by": sort_by,
            "file_types": file_types, "size_distribution": size_distribution,
        }

        if total > LISTDIR_PAGE_SIZE:
            logger.warning(f"[listdir] Large directory truncated: path={path}, total={total}")

        list_data = _build_list_success(all_entries, total, path, statistics, start_offset, LISTDIR_PAGE_SIZE)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        exec_code = "warning" if list_data["truncated"] else "success"
        llm_data = _build_list_directory_llm_data(exec_code, duration_ms, dir_path=dir_path, total=total, truncated=list_data["truncated"])
        if exec_code == "warning":
            return build_warning(data=list_data, llm_data=llm_data)
        return build_success(data=list_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to list directory {dir_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"dir_path": dir_path}}, llm_data=llm_data)