# -*- coding: utf-8 -*-
"""
F7: grep_file_content — 搜索文件内容

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import re as re_mod
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS, MAX_SEARCH_FILE_SIZE
from app.constants import ERR_FILE_CONTENT_SEARCH_FAILED
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


_ENCODING_PRIORITY = ["utf-8", "gbk", "gb2312", "utf-8-sig"]


def _read_file_safe(file_path: Path) -> List[str]:
    """多编码尝试读取文件行 — 小健 2026-05-25 — 小欧 2026-06-22"""
    try:
        size = file_path.stat().st_size
        if size > MAX_SEARCH_FILE_SIZE:
            return []
    except OSError:
        return []
    for enc in _ENCODING_PRIORITY:
        try:
            with file_path.open("r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def _build_grep_file_content_llm_data(
    exec_code: str, duration_ms: int,
    pattern: str = "", search_dir: str = "",
    total_files: int = 0, total_matches: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """grep_file_content的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"内容搜索失败: {detail}",
            "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_CONTENT_SEARCH_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"搜索完成: 匹配{total_matches}行, {total_files}个文件",
        "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "total_files": {"value": total_files, "text": f"{total_files}个文件"},
            "total_matches": {"value": total_matches, "text": f"{total_matches}行"},
        },
    }


def _grep_files_sync(
    search_dir: Path, pattern: str, glob_filter: Optional[str],
    ignore_case: bool, deadline: float,
) -> Tuple[List[Dict], int, int]:
    """同步搜索文件内容 — 小欧 2026-06-22"""
    results = []
    total_matches = 0
    total_files = 0
    flags = re_mod.IGNORECASE if ignore_case else 0
    try:
        regex = re_mod.compile(pattern, flags)
    except re_mod.error as e:
        return [], 0, 0

    for root, dirs, files in os.walk(search_dir):
        if time.monotonic() > deadline:
            break
        for fname in files:
            if time.monotonic() > deadline:
                break
            fpath = Path(root) / fname
            if glob_filter:
                import fnmatch as fnm
                if not fnm.fnmatch(fname, glob_filter):
                    continue
            lines = _read_file_safe(fpath)
            if not lines:
                continue
            file_matches = []
            for line_no, line in enumerate(lines, 1):
                m = regex.search(line)
                if m:
                    file_matches.append({
                        "file": str(fpath),
                        "line": line_no,
                        "content": line.rstrip('\n\r'),
                    })
                    total_matches += 1
            if file_matches:
                total_files += 1
                results.extend(file_matches)

    return results, total_files, total_matches


import os


async def grep_file_content(
    pattern: str,
    search_dir: Optional[str] = None,
    glob: Optional[str] = None,
    ignore_case: bool = True,
) -> Dict[str, Any]:
    """搜索文件内容 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    actual_dir = search_dir or "."
    is_valid, error_msg = _validate_path(actual_dir)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=error_msg)
        return build_error(data={"error_detail": error_msg, "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    if not pattern or not pattern.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail="搜索模式不能为空")
        return build_error(data={"error_detail": "搜索模式不能为空", "params": {"pattern": pattern}}, llm_data=llm_data)

    try:
        regex = re_mod.compile(pattern, re_mod.IGNORECASE if ignore_case else 0)
    except re_mod.error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=f"正则表达式无效: {e}")
        return build_error(data={"error_detail": f"正则表达式无效: {e}", "params": {"pattern": pattern}}, llm_data=llm_data)

    search_path = Path(os.path.expanduser(actual_dir))
    if not search_path.exists():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=f"搜索目录不存在: {actual_dir}")
        return build_error(data={"error_detail": "搜索目录不存在", "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    deadline = time.monotonic() + TOOL_TIMEOUTS.get("grep_file_content", TOOL_TIMEOUTS["default"]) - 2

    try:
        results, total_files, total_matches = await asyncio.to_thread(
            _grep_files_sync, search_path, pattern, glob, ignore_case, deadline,
        )
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    llm_data = _build_grep_file_content_llm_data(
        "success", duration_ms, pattern=pattern, search_dir=actual_dir,
        total_files=total_files, total_matches=total_matches,
    )
    return build_success(
        data={"matches": results, "total_matches": total_matches, "total_files": total_files, "pattern": pattern},
        llm_data=llm_data,
    )