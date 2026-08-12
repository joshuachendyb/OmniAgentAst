# -*- coding: utf-8 -*-
"""find 文件搜索工具 — 文件名匹配搜索(支持正则/通配符/类型过滤)"""
# 编辑历史:
# 2026-07-20 - 小欧 - find 门限治理(章7.4): 移除 MAX_SEARCH_RESULTS 收集上限与 max_depth=50 递归限制; 移除 FIND_PAGE_SIZE 分页, 返回全部匹配(offset 仅作跳过); 截断唯一收口于 observation_formatter OBS_FIND_MAX_ROWS/CHARS(两态说明); deadline 超时保留为保护
# 2026-07-20 - 小欧 - 门限复查: 删 _is_already_seen_or_skipped 去重/跳过死逻辑(seen_files/start_offset 恒0, os.walk 不重复致 dup/skip 永False)及未用 Tuple import; 直接 _collect_entry_result, 行为不变
# 2026-08-06 - 小欧 - 核查7/31未实现项[14]修复: 新增_SKIP_DIRS常量(os.walk剪枝跳过大目录), 避免node_modules/.git等大目录拖慢find超时
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints

import asyncio
import fnmatch
import os
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.tools.tool_constants import ERR_FILE_SEARCH_FAILED
from app.tools.validate.file_path_checker import validate_path, OpCategory  # 统一错误提示 - 小欧 2026-07-12
from app.tools.toolhelper.error_hints import hint_for_read_error
from app.logger import logger

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".idea", ".vscode", ".svn", ".hg", ".pytest_cache", "site-packages",
})  # find剪枝跳过大目录 — 小欧 2026-08-06


def _match_fnmatch(name: str, pattern: str, ignore_case: bool) -> bool:
    """统一封装fnmatch — 小健 2026-05-25 — 小欧 2026-06-22"""
    if ignore_case:
        return fnmatch.fnmatch(name.lower(), pattern.lower())
    return fnmatch.fnmatch(name, pattern)


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
        detail_parts = [f"总数{total}条"]
        _timeout_str = ""
        if truncated_by_deadline:
            _timeout_str = f"，超时({_timeout_sec}秒)"
        warning_detail = "; ".join(detail_parts)
        _default_hint = "可缩小搜索范围或使用更精确的匹配模式以减少匹配数量; 或使用 offset 跳过前 N 项分批查看"
        return {
            "summary": f"在 {search_dir} 中搜索 '{user_pattern}' 完成，共 {total} 个匹配项，结果已截断{_timeout_str}",
            "action": {"tool": "find", "tool_zh": "搜索文件", "target": search_dir, "params": _act_params},
            "status": {"exec_code": "warning", "message": "搜索结果不完整", "code": "", "detail": warning_detail, "hint": hint if hint else _default_hint},
            "duration_ms": duration_ms,
            "metrics": {
                "total": {"value": total, "text": f"{total}个匹配"},
            },
        }
    summary = f"在 {search_dir} 中搜索 '{user_pattern}' 完成，共 {total} 个匹配项"
    if user_offset:
        summary += f"，第{user_offset+1}-{total}项"
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

    def _search_sync():
        for root, dirs, files in os.walk(path):
            if _time_mod.monotonic() > deadline:
                logger.warning(f"[find] 超时自检触发,提前返回{len(all_matches)}个匹配")
                break
            # 剪枝跳过大目录, 避免 node_modules/.git 等拖慢搜索 — 小欧 2026-08-06
            if dirs:
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            if type != "file":
                for d in dirs:
                    if not _match_fnmatch(d, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, d), path)
                    _collect_entry_result(relative, d, Path(os.path.join(root, d)), all_matches, llm_preview)
            if type != "directory":
                for f in files:
                    if not _match_fnmatch(f, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, f), path)
                    _collect_entry_result(relative, f, Path(os.path.join(root, f)), all_matches, llm_preview)

    try:
        await asyncio.to_thread(_search_sync)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"搜索失败: {e}", hint=hint_for_read_error(e, Path(search_dir).name), user_pattern=pattern, user_ignore_case=ignore_case, user_type=type, user_offset=offset)  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)

    all_matches.sort(key=lambda x: x.get("name", ""))
    total = len(all_matches)
    page = all_matches[offset:]
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    truncated_by_deadline = _time_mod.monotonic() > deadline
    exec_code = "warning" if truncated_by_deadline else "success"
    llm_data = _build_search_files_llm_data(
        exec_code, duration_ms,
        search_dir=search_dir, total=total,
        truncated=truncated_by_deadline,
        user_pattern=pattern, user_ignore_case=ignore_case,
        user_type=type, user_offset=offset,
        truncated_by_deadline=truncated_by_deadline,
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
