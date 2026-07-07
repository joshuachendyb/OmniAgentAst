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
from typing import Any, Dict, List, Optional, Tuple

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
    """构建单个目录条目 -- 小健 2026-05-25 -- 小欧 2026-06-22 — 小欧 2026-07-06 去path/mtime，size仅文件"""
    is_dir = item.is_dir()
    entry: Dict[str, Any] = {"name": item.name, "type": "directory" if is_dir else "file"}
    if not is_dir:
        entry["size"] = st.st_size
    return entry


def _scan_directory_sync(
    path: Path, recursive: bool, max_depth: int,
    include_hidden: bool, deadline: float,
) -> Tuple[List[Dict], Dict, Dict, Dict, bool]:
    """同步扫描目录 — 小健 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-07-07 返回timed_out"""
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

    return entries, stats, ext_counter, size_bins, _timed_out


def _build_list_success(entries: List, total: int,
                         start_offset: int,
                         max_display: int) -> Dict[str, Any]:
    """构建list模式的原始数据 — 小健 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-07-06 去statistics"""
    truncated = total > max_display
    display_entries = entries[start_offset:start_offset + max_display]
    return {
        "entries": display_entries,
        "truncated": truncated,
    }


def _build_list_directory_llm_data(
    exec_code: str, duration_ms: int,
    dir_path: str = "", total: int = 0,
    truncated: bool = False, detail: str = "",
    hint: str = "",
    user_sort_by: str = "", user_include_hidden: Optional[bool] = None,
    user_offset: int = 0,
    dir_count: int = 0, file_count: int = 0, total_size: int = 0,
    file_types: Optional[Dict[str, int]] = None,
    size_distribution: Optional[Dict[str, int]] = None,
    timed_out: bool = False,
) -> Dict[str, Any]:
    """list_directory的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数 — 小欧 2026-07-06 statistics移入metrics/summary — 小欧 2026-07-07 超时秒数"""
    _listdir_timeout_sec = TOOL_TIMEOUTS.get("list_directory", TOOL_TIMEOUTS["default"])
    _act_params = {"dir_path": dir_path}
    if user_sort_by:
        _act_params["sort_by"] = user_sort_by
    if user_include_hidden is not None:
        _act_params["include_hidden"] = user_include_hidden
    if user_offset:
        _act_params["offset"] = user_offset
    if exec_code == "error":
        return {
            "summary": f"列出目录{dir_path}，失败",
            "action": {"tool": "listdir", "tool_zh": "列出目录", "target": dir_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "列出目录失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": hint if hint else "请检查目录路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    m: Dict[str, Any] = {
        "total": {"value": total, "text": f"{total}项"},
        "dir_count": {"value": dir_count, "text": f"{dir_count}个目录"},
        "file_count": {"value": file_count, "text": f"{file_count}个文件"},
        "total_size": {"value": total_size, "text": f"{total_size}字节"},
    }
    if exec_code == "warning":
        m["truncated"] = {"value": True, "text": "已截断"}
        warning_detail = detail if detail else f"总数{total}条, 输出前{LISTDIR_PAGE_SIZE}条"
        warning_hint = hint if hint else "请使用更精确的路径或筛选条件"
        _summary_suffix = f"，超时({_listdir_timeout_sec}秒)" if timed_out else "，已截断"
        return {
            "summary": f"列出目录{dir_path}，成功,提示说明: {total}项，{file_count}个文件，{dir_count}个目录{_summary_suffix}",
            "action": {"tool": "listdir", "tool_zh": "列出目录", "target": dir_path, "params": _act_params},
            "status": {"exec_code": "warning", "message": "目录内容不完整", "code": "", "detail": warning_detail, "hint": warning_hint},
            "duration_ms": duration_ms,
            "metrics": m,
        }
    summary = f"列出目录{dir_path}，成功: {total}项，{file_count}个文件，{dir_count}个目录"
    if user_offset:
        end_offset = min(user_offset + LISTDIR_PAGE_SIZE, total)
        summary += f"，第{user_offset+1}-{end_offset}项"
    return {
        "summary": summary,
        "action": {"tool": "listdir", "tool_zh": "列出目录", "target": dir_path, "params": _act_params},
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
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail="dir_path不能为空", hint="请提供有效的目录路径", user_sort_by=sort_by, user_include_hidden=include_hidden, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)

    if sort_by not in ("name", "size"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name'/'size',当前值: '{sort_by}'", hint="sort_by参数只能为name或size", user_sort_by=sort_by, user_include_hidden=include_hidden, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)

    if offset < 0:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"offset必须>=0,当前值: {offset}", hint="offset从0开始,负值无效", user_sort_by=sort_by, user_include_hidden=include_hidden, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)

    path = Path(dir_path)
    start_offset = offset

    try:
        # 工具层校验：非空/保留字符/保留名/系统目录/路径存在+是目录 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.LIST_DIR, dir_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=err, hint="请检查目录路径是否正确", user_sort_by=sort_by, user_include_hidden=include_hidden, user_offset=offset)
            return build_error(data={}, llm_data=llm_data)

        deadline = _time_mod.monotonic() + TOOL_TIMEOUTS.get("list_directory", TOOL_TIMEOUTS["default"]) - 2
        all_entries, stats, file_types, size_distribution, _scan_timed_out = await asyncio.to_thread(
            _scan_directory_sync, path, False, 10, include_hidden, deadline,
        )

        if sort_by == "size":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("size") or 0), reverse=True)
        else:
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

        total = len(all_entries)

        if total > LISTDIR_PAGE_SIZE:
            logger.warning(f"[listdir] Large directory truncated: path={path}, total={total}")

        list_data = _build_list_success(all_entries, total, start_offset, LISTDIR_PAGE_SIZE)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        exec_code = "warning" if (list_data["truncated"] or _scan_timed_out) else "success"
        llm_data = _build_list_directory_llm_data(
            exec_code, duration_ms,
            dir_path=dir_path, total=total,
            truncated=list_data["truncated"],
            user_sort_by=sort_by, user_include_hidden=include_hidden,
            user_offset=offset,
            dir_count=stats["dir_count"], file_count=stats["file_count"],
            total_size=stats["total_size"],
            file_types=file_types, size_distribution=size_distribution,
            timed_out=_scan_timed_out,
        )
        # =============================================================================
        # 数据设计：total/statistics 从 data 移除，
        # dir_count/file_count/total_size/file_types/size_distribution 移入 llm_data.metrics
        # summary 示例: "列出目录成功: /path (47项, 42个文件, 5个目录)"
        # — 小欧 2026-07-06
        # =============================================================================
        if exec_code == "warning":
            # ---- observation_formatter route -------------------------------------------
            # branch: #3 entries
            # trigger: "entries" in data — entries 是 List[dict]
            # handler: _format_entries(data["entries"])
            # file:    observation_formatter.py:128-130
            # ------------------------------------------------------------------------------
            return build_warning(data=list_data, llm_data=llm_data)
        # ---- observation_formatter route -------------------------------------------
        # branch: #3 entries
        # trigger: "entries" in data — entries 是 List[dict]
        # handler: _format_entries(data["entries"])
        # file:    observation_formatter.py:128-130
        # ------------------------------------------------------------------------------
        return build_success(data=list_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to list directory {dir_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=str(e), hint="请检查目录路径和访问权限", user_sort_by=sort_by, user_include_hidden=include_hidden, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)