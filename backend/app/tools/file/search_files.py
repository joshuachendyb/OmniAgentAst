# -*- coding: utf-8 -*-
"""
F6: search_files — 搜索文件名

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import fnmatch
import os
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import TOOL_TIMEOUTS, FIND_PAGE_SIZE, MAX_SEARCH_RESULTS
from app.tools.tool_constants import ERR_FILE_SEARCH_FAILED
from app.tools.validate.file_path_checker import validate_path, OpCategory, hint_for_read_error  # 统一错误提示 - 小欧 2026-07-12
from app.logger import logger


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
    search_dir: str = "", total: int = 0,
    truncated: bool = False, detail: str = "", hint: str = "",
    user_pattern: str = "", user_ignore_case: Optional[bool] = None,
    user_type: Optional[str] = None, user_offset: int = 0,
    truncated_by_deadline: bool = False,
    truncated_by_limit: bool = False,
    truncated_by_offset: bool = False,
    reached_cap: bool = False,
) -> Dict[str, Any]:
    """search_files的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小健 2026-06-23 添加结果数量限制提示 — 小欧 2026-07-06 summary含路径/模式/页码, warning用常量 — 小欧 2026-07-07 超时秒数"""
    _timeout_sec = TOOL_TIMEOUTS.get("find", TOOL_TIMEOUTS["default"])
    _act_params = {"path": search_dir}
    if user_pattern:
        _act_params["pattern"] = user_pattern
    if user_ignore_case is not None:
        _act_params["ignore_case"] = user_ignore_case
    if user_type:
        _act_params["type"] = user_type
    if user_offset:
        _act_params["offset"] = user_offset
    if exec_code == "error":
        return {
            "summary": f"搜索文件{search_dir}，失败",
            "action": {"tool": "find", "tool_zh": "搜索文件", "target": search_dir, "params": _act_params},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_SEARCH_FAILED, "detail": detail, "hint": hint if hint else "请检查搜索目录和匹配模式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        detail_parts = [f"总数{total}条, 输出前{min(FIND_PAGE_SIZE, total)}条"]
        _timeout_str = ""
        if truncated_by_deadline:
            _timeout_str = f"，超时({_timeout_sec}秒)"
        if truncated_by_limit:
            detail_parts.append("结果数量达到上限")
        if truncated_by_offset:
            detail_parts.append("分页截断")
        if reached_cap:
            detail_parts.append("已到结果上限,无更多结果")
        warning_detail = "; ".join(detail_parts)
        # 翻页引导提示:已匹配的MAX_SEARCH_RESULTS条可用offset分页获取 — 小欧 2026-07-12
        _default_hint = f"可使用offset参数分页获取已匹配的{MAX_SEARCH_RESULTS}条结果,或缩小搜索范围/使用更精确匹配模式"
        return {
            "summary": f"在 {search_dir} 中搜索 '{user_pattern}' 完成，共 {total} 个匹配项，结果已截断{_timeout_str}",
            "action": {"tool": "find", "tool_zh": "搜索文件", "target": search_dir, "params": _act_params},
            "status": {"exec_code": "warning", "message": "已到达结果上限" if reached_cap else "搜索结果不完整", "code": "", "detail": warning_detail, "hint": hint if hint else _default_hint},
            "duration_ms": duration_ms,
            "metrics": {
                "total": {"value": total, "text": f"{total}个匹配"},
            },
        }
    summary = f"在 {search_dir} 中搜索 '{user_pattern}' 完成，共 {total} 个匹配项"
    if user_offset:
        end = min(user_offset + FIND_PAGE_SIZE, total)
        summary += f"，第{user_offset+1}-{end}项"
    return {
        "summary": summary,
        "action": {"tool": "find", "tool_zh": "搜索文件", "target": search_dir, "params": _act_params},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "total": {"value": total, "text": f"{total}个匹配"},
        },
    }


async def find(
    pattern: str,
    path: str,
    ignore_case: bool = True,
    type: Optional[Literal["file", "directory"]] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    """搜索文件名(始终递归搜索子目录) — 小沈 2026-05-19 — 小欧 2026-06-22 — 小欧 2026-06-23 去掉recursive — 小欧 2026-07-04 offset分页 — 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量search_dir — 小欧 2026-07-11
    search_dir = path
    t0 = _time_mod.perf_counter()
    max_depth = 50
    if type is not None and type not in ("file", "directory"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"type参数只能为'file'或'directory',当前值: '{type}'", hint="请使用file或directory作为type参数", user_pattern=pattern, user_ignore_case=ignore_case, user_type=type, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)
    if not pattern or not pattern.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail="文件名匹配模式不能为空", hint="请输入文件名匹配模式", user_pattern=pattern, user_ignore_case=ignore_case, user_type=type, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)
    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在+是目录 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.LIST_DIR, search_dir)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=err, hint="请检查搜索目录路径", user_pattern=pattern, user_ignore_case=ignore_case, user_type=type, user_offset=offset)
        return build_error(data={}, llm_data=llm_data)

    path = Path(os.path.expanduser(search_dir))

    deadline = _time_mod.monotonic() + TOOL_TIMEOUTS.get("find", TOOL_TIMEOUTS["default"]) - 2
    all_matches: List = []
    llm_preview: List = []
    seen_files: set = set()
    start_offset = 0

    def _search_sync():
        nonlocal seen_files
        for root, dirs, files in os.walk(path):
            if _time_mod.monotonic() > deadline:
                logger.warning(f"[find] 超时自检触发,提前返回{len(all_matches)}个匹配")
                break
            if len(all_matches) >= MAX_SEARCH_RESULTS:
                logger.warning(f"[find] 结果数量达到上限{MAX_SEARCH_RESULTS},提前返回")
                break
            if max_depth:
                depth = root[len(str(path)):].count(os.sep)
                if depth >= max_depth:
                    dirs.clear()
            if type != "file":
                for d in dirs:
                    if len(all_matches) >= MAX_SEARCH_RESULTS:
                        break
                    if not _match_fnmatch(d, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, d), path)
                    dup, skip = _is_already_seen_or_skipped(relative, seen_files, len(all_matches), start_offset)
                    if dup or skip:
                        continue
                    _collect_entry_result(relative, d, Path(os.path.join(root, d)), all_matches, llm_preview)
                    seen_files.add(relative)
            if type != "directory":
                for f in files:
                    if len(all_matches) >= MAX_SEARCH_RESULTS:
                        break
                    if not _match_fnmatch(f, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, f), path)
                    dup, skip = _is_already_seen_or_skipped(relative, seen_files, len(all_matches), start_offset)
                    if dup or skip:
                        continue
                    _collect_entry_result(relative, f, Path(os.path.join(root, f)), all_matches, llm_preview)
                    seen_files.add(relative)

    try:
        await asyncio.to_thread(_search_sync)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"搜索失败: {e}", hint=hint_for_read_error(e, Path(search_dir).name), user_pattern=pattern, user_ignore_case=ignore_case, user_type=type, user_offset=offset)  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)

    all_matches.sort(key=lambda x: x.get("name", ""))
    total = len(all_matches)
    page = all_matches[offset:offset + FIND_PAGE_SIZE]
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    truncated_by_deadline = _time_mod.monotonic() > deadline
    truncated_by_limit = total >= MAX_SEARCH_RESULTS
    truncated_by_offset = total > (offset + FIND_PAGE_SIZE)
    # 已达收集上限且本页无数据(offset越界):明确提示"已到上限",消除静默空页 — 小欧 2026-07-12
    reached_cap = truncated_by_limit and len(page) == 0
    exec_code = "warning" if (truncated_by_deadline or truncated_by_limit or truncated_by_offset or reached_cap) else "success"
    llm_data = _build_search_files_llm_data(
        exec_code, duration_ms,
        search_dir=search_dir, total=total,
        truncated=(truncated_by_deadline or truncated_by_limit or truncated_by_offset or reached_cap),
        user_pattern=pattern, user_ignore_case=ignore_case,
        user_type=type, user_offset=offset,
        truncated_by_deadline=truncated_by_deadline,
        truncated_by_limit=truncated_by_limit,
        truncated_by_offset=truncated_by_offset,
        reached_cap=reached_cap,
    )
    if exec_code == "warning":
        # ---- observation_formatter route -------------------------------------------
        # branch: #9 matches (find subtype)
        # trigger: "matches" in data → ms[0] 含 "path" 键
        # handler: _format_find_results(ms)
        # file:    observation_formatter.py:152-178
        # ------------------------------------------------------------------------------
        # =============================================================================
        # 数据设计：total/search_dir/pattern/offset 从 data 移除，
        # 通过 llm_data.metrics/summary 传入 LLM observation。
        # summary 示例: "搜索完成: /path 下匹配 '*.py', 共15个匹配"
        # — 小欧 2026-07-06
        # =============================================================================
        return build_warning(
            data={"matches": page},
            llm_data=llm_data,
        )
    # ---- observation_formatter route -------------------------------------------
    # branch: #9 matches (find subtype)
    # trigger: "matches" in data → ms[0] 含 "path" 键
    # handler: _format_find_results(ms)
    # file:    observation_formatter.py:152-178
    # ------------------------------------------------------------------------------
    # =============================================================================
    # 数据设计：total/search_dir/pattern/offset 从 data 移除，
    # 通过 llm_data.metrics/summary 传入 LLM observation。
    # summary 示例: "搜索完成: /path 下匹配 '*.py', 共15个匹配, 第1-200项"
    # — 小欧 2026-07-06
    # =============================================================================
    return build_success(
        data={"matches": page},
        llm_data=llm_data,
    )