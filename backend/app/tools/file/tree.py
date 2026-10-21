# -*- coding: utf-8 -*-
# 2026-10-04 小欧 - obs方案A: 删action.target(params承载目标)+document params file_path→path
# 编辑历史:
# 2026-07-20 - 小欧 - 自然单位页感知 feat:
#   1. 新增 statistics(file/dir/size) 数据
#   2. formatter 层级感知截断用
# 2026-07-20 - 小欧 - 去噪去重 refactor:
#   移除 statistics(data/llm_data 重复)
# 2026-10-12 小欧 - tool_zh改短名词: 列出目录树→列目录
# 2026-10-16 - 小欧 - tool去检查化: 删 validate_path 合法性检查(归 路径安全层), 工具只执行。
# 2026-10-17 小欧 - 接入 path_utils.check_path_four_level 四级合法性总入口(读类用 EXISTS)
# 2026-10-19 小欧 - 入参须为目录: 原实现对文件路径静默产出伪目录节点(iterdir 的
#   NotADirectoryError 被 _build_tree 当 OSError 吞掉且 node 无条件标 type=directory);
#   入口补 is_dir 校验, 非目录如实返回错误。
# 2026-10-21 小杨 - 列目录工具落码：单遍 scandir 同时建树与统计（IO 减半）、
#   加目录节点数与扫描条目数双闸门（超限置 truncated 并在摘要标注）、
#   目录计数只统计实际入树的目录、mtime 排序改为最近修改优先 — 小杨-2026-10-21
"""
tree — 列出目录树 (从list_directory拆分，仅列目录)

从list_directory.py拆分而来 — 小沈 2026-07-03 — 小欧 2026-07-06 删_build_entry/node去size/mtime/sort_by去mtime
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import asyncio
import time as _time_mod
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_FILE_LIST_DIR_FAILED

from app.logger import logger
from app.utils.path_utils import OpCategory, check_path_four_level  # 2026-10-17 小欧 - 路径四级合法性总入口

# 2026-10-21 小杨 - 修复：max_depth=10 对超大目录不设上限会吃光内存/把
#   Agent 调用拖到超时；给"目录节点数 + 扫描条目数"双闸门，超限如实置 truncated。
_MAX_DIRS = 20000
_MAX_ENTRIES = 200000


async def _get_directory_tree(
    dir_path: str, max_depth: int = 5,
    include_hidden: bool = False,
    sort_by: str = "name",
) -> Dict[str, Any]:
    """获取目录树原始数据（单遍 scandir 同时建树与统计，IO 减半）"""
    # 2026-10-16 小欧 - tool去检查化: 合法性由 路径安全层 唯一检查, 工具只执行
    def _name_key(e: os.DirEntry) -> str:
        return e.name.lower()

    def _mtime_key(e: os.DirEntry) -> float:
        try:
            return e.stat().st_mtime
        except OSError:
            return 0.0

    state = {"dirs": 0, "entries": 0, "truncated": False}

    def _scan_dir(dir_str: str, depth: int, _visited: set) -> Tuple[Optional[Dict[str, Any]], int, int, int]:
        """单遍扫描：一次 scandir 同时建树+统计(fc/dc/bytes)。
        Windows 上 scandir 的 entry.is_dir(follow_symlinks=False) 零额外 syscall；
        只对 symlink 目录查 realpath 成环（普通目录不成环，省掉每目录一次 resolve）。
        2026-10-21 小杨 - 修复：统计口径与返回树对齐（dc 只计实际入树目录），
        并加目录数/条目数上限，超限置 state["truncated"]，不再无限膨胀。"""
        if depth > max_depth:
            return None, 0, 0, 0
        try:
            ctx = os.scandir(dir_str)
        except (PermissionError, OSError):
            return None, 0, 0, 0
        dir_entries: list = []
        fc = dc = ts = 0
        with ctx:
            for entry in ctx:
                state["entries"] += 1
                if state["entries"] > _MAX_ENTRIES:
                    state["truncated"] = True
                    break
                if not include_hidden and entry.name.startswith('.'):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dir_entries.append(entry)
                    else:
                        fc += 1
                        try:
                            ts += entry.stat().st_size
                        except OSError:
                            pass
                except (PermissionError, OSError):
                    continue
        # 2026-10-21 小杨 - 修复：mtime 语义是"最近修改优先"（前端排序习惯），
        #   原实现升序 → 最旧的在最前；工具契约与用例均要求最新在前。
        dir_entries.sort(
            key=_mtime_key if sort_by == "mtime" else _name_key,
            reverse=(sort_by == "mtime"),
        )

        children: list = []
        for entry in dir_entries:
            if state["dirs"] >= _MAX_DIRS:
                state["truncated"] = True
                break
            if entry.is_symlink():
                try:
                    real = os.path.realpath(entry.path, strict=False)
                except OSError:
                    real = entry.path
                if real in _visited:
                    logger.warning(f"[tree] 跳过循环符号链接: {entry.path}")
                    continue
                _visited.add(real)
            else:
                _visited.add(os.path.normcase(entry.path))
            child, c_fc, c_dc, c_ts = _scan_dir(entry.path, depth + 1, _visited)
            if child is not None:
                children.append(child)
                fc += c_fc
                dc += c_dc
                ts += c_ts
                dc += 1                      # 2026-10-21 小杨 - 只统计真正入树的目录（原实现把被跳过/截断的也计入，与 tree 不一致）
                state["dirs"] += 1

        node: Dict[str, Any] = {
            "name": os.path.basename(dir_str.rstrip('\\/')) or dir_str,
            "path": os.path.abspath(dir_str),
            "type": "directory",
            "children": children,
        }
        return node, fc, dc, ts

    def _run() -> Tuple[Optional[Dict[str, Any]], int, int, int]:
        visited: set = set()
        visited.add(os.path.normcase(dir_path))
        return _scan_dir(dir_path, 0, visited)

    tree, fc, dc, ts = await asyncio.to_thread(_run)
    if tree is None:
        return {"error_detail": "查询目录树失败", "params": {"path": dir_path}}
    result: Dict[str, Any] = {
        "tree": tree,
        "statistics": {"file_count": fc, "dir_count": dc, "total_size": ts},
    }
    if state["truncated"]:
        result["truncated"] = True
    return result



def _build_tree_llm_data(
    exec_code: str, duration_ms: int,
    dir_path: str = "", total: int = 0, detail: str = "", hint: str = "",
    user_include_hidden: Optional[bool] = None, user_sort_by: str = "",
    file_count: int = 0, dir_count: int = 0,
    truncated: bool = False,
) -> Dict[str, Any]:
    """tree的llm_data构建函数 — 小沈 2026-07-03 — 小沈 2026-07-05 新增hint参数 — 小欧 2026-07-07 summary加file/dir明细"""
    _act_params = {"path": dir_path}
    if user_include_hidden is not None:
        _act_params["include_hidden"] = user_include_hidden
    if user_sort_by:
        _act_params["sort_by"] = user_sort_by
    if exec_code == "error":
        return {
            "summary": f"列目录{dir_path}，失败",
            "action": {"tool": "tree", "tool_zh": "列目录", "params": _act_params},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": hint if hint else "请检查目录路径和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _trunc = "（目录节点数超限，已截断）" if truncated else ""
    return {
        "summary": f"列目录{dir_path}，成功：{file_count}个文件，{dir_count}个目录{_trunc}",  # 2026-10-14 小欧 - summary 统一口径: 动词用 tool_zh(列目录) — 小欧-2026-10-14
        "action": {"tool": "tree", "tool_zh": "列目录", "params": _act_params},
        "status": {"exec_code": "success", "message": f"成功：{file_count}个文件，{dir_count}个目录{_trunc}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"total": {"value": total, "text": f"{total}项"}},
    }


async def tree(
    path: str,
    include_hidden: bool = False,
    max_depth: int = 10,
    sort_by: str = "name",
) -> Dict[str, Any]:
    """列出目录树 — 小沈 2026-07-03 从list_directory拆分 — 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量dir_path — 小欧 2026-07-11
    dir_path = path
    t0 = _time_mod.perf_counter()
    # 2026-10-17 小欧 - 路径检查走 check_path_four_level 四级合法性总入口(读类用 EXISTS)
    ok, err = check_path_four_level(dir_path, OpCategory.EXISTS)
    if not ok:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path, detail=err, hint="请检查目录路径", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={}, llm_data=llm_data)
    # 2026-10-19 小欧 - 入参须为目录(见文件头编辑历史): 文件路径不再静默产出伪目录
    if not Path(dir_path).is_dir():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path, detail=f"路径不是目录: {dir_path}", hint="请提供目录路径", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={}, llm_data=llm_data)
    if max_depth < 1:
        max_depth = 1

    if not dir_path or not dir_path.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail="dir_path不能为空", hint="请提供目录路径", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={}, llm_data=llm_data)

    if sort_by not in ("name", "mtime"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name'/'mtime'，当前值：'{sort_by}'", hint="sort_by只能为name或mtime", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={}, llm_data=llm_data)

    tree_result = await _get_directory_tree(dir_path=dir_path, max_depth=max_depth, include_hidden=include_hidden, sort_by=sort_by)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if "error_detail" in tree_result:
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=tree_result["error_detail"], hint="请检查目录路径是否正确", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data=tree_result, llm_data=llm_data)
    else:
        file_count = tree_result["statistics"]["file_count"]
        dir_count = tree_result["statistics"]["dir_count"]
        total = file_count + dir_count
        llm_data = _build_tree_llm_data("success", duration_ms, dir_path=dir_path, total=total, file_count=file_count, dir_count=dir_count, user_include_hidden=include_hidden, user_sort_by=sort_by, truncated=bool(tree_result.get("truncated")))
        # ---- observation_formatter route -------------------------------------------
        # branch: #12 tree
        # trigger: "tree" in data and isinstance(data.get("tree"), dict)
        # handler: _format_tree(data) — 嵌套dict→可视化树形字符串
        # file:    observation_formatter.py:184-186
        # ------------------------------------------------------------------------------
        return build_success(data=tree_result, llm_data=llm_data)
