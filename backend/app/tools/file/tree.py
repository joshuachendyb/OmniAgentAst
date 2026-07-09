# -*- coding: utf-8 -*-
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
from app.tools.validate.file_path_checker import validate_path, OpCategory
from app.utils.logger import logger


async def _get_directory_tree(
    dir_path: str, max_depth: int = 5,
    include_hidden: bool = False,
) -> Dict[str, Any]:
    """获取目录树原始数据 — 小欧 2026-06-22 — 小健 2026-06-22 删除helper计时 — 小欧 2026-06-24 修复include_hidden — 小欧 2026-07-06 去mtime排序"""
    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在+是目录 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.LIST_DIR, dir_path)
    if not is_valid:
        return {"error_detail": err, "params": {"dir_path": dir_path}}

    path = Path(dir_path)

    def _count_tree_fs(root: Path, depth: int = 0) -> Tuple[int, int, int]:
        fc = dc = ts = 0
        try:
            for entry in os.scandir(root):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        dc += 1
                        if depth < max_depth:  # 与 _build_tree 深度一致 — 小沈 2026-07-08
                            sub_f, sub_d, sub_s = _count_tree_fs(Path(entry.path), depth + 1)
                            fc += sub_f; dc += sub_d; ts += sub_s
                    else:
                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        fc += 1
                        ts += entry.stat().st_size
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass
        return fc, dc, ts

    def _sort_items(items):
        """按名称排序目录项 """
        return sorted(items, key=lambda x: x.name.lower())

    def _build_tree(current_path: Path, depth: int = 0, _visited: Optional[set] = None) -> Optional[Dict[str, Any]]:
        if _visited is None:
            _visited = set()
        resolved = current_path.resolve()
        if resolved in _visited:
            logger.warning(f"[tree] 跳过循环符号链接: {current_path}")
            return None
        _visited.add(resolved)
        if depth > max_depth:
            return None
        try:
            current_path.stat()  # 只检查权限，返回值不用
        except OSError:
            return None
        node: Dict[str, Any] = {
            "name": current_path.name,
            "path": str(current_path.absolute()),
            "type": "directory",
        }
        children: list = []
        try:
            items = [item for item in current_path.iterdir() if item.is_dir()]
            if not include_hidden:
                items = [item for item in items if not item.name.startswith('.')]
            for item in _sort_items(items):
                child = _build_tree(item, depth + 1, _visited)
                if child:
                    children.append(child)
        except (PermissionError, OSError):
            pass
        node["children"] = children
        return node

    tree = await asyncio.to_thread(_build_tree, path)
    if tree is None:
        return {"error_detail": "构建目录树失败", "params": {"dir_path": dir_path}}

    fc, dc, ts = await asyncio.to_thread(_count_tree_fs, path)
    return {"tree": tree, "statistics": {"file_count": fc, "dir_count": dc, "total_size": ts}}


def _build_tree_llm_data(
    exec_code: str, duration_ms: int,
    dir_path: str = "", total: int = 0, detail: str = "", hint: str = "",
    user_include_hidden: Optional[bool] = None, user_sort_by: str = "",
    file_count: int = 0, dir_count: int = 0,
) -> Dict[str, Any]:
    """tree的llm_data构建函数 — 小沈 2026-07-03 — 小沈 2026-07-05 新增hint参数 — 小欧 2026-07-07 summary加file/dir明细"""
    _act_params = {"dir_path": dir_path}
    if user_include_hidden is not None:
        _act_params["include_hidden"] = user_include_hidden
    if user_sort_by:
        _act_params["sort_by"] = user_sort_by
    if exec_code == "error":
        return {
            "summary": f"列出目录树{dir_path}，失败",
            "action": {"tool": "tree", "tool_zh": "列出目录树", "target": dir_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "列出目录树失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": hint if hint else "请检查目录路径和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"列出目录树{dir_path}，成功: {file_count}个文件，{dir_count}个目录",
        "action": {"tool": "tree", "tool_zh": "列出目录树", "target": dir_path, "params": _act_params},
        "status": {"exec_code": "success", "message": "列出目录树成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"total": {"value": total, "text": f"{total}项"}},
    }


async def tree(
    dir_path: str,
    include_hidden: bool = False,
    max_depth: int = 5,
    sort_by: str = "name",
) -> Dict[str, Any]:
    """列出目录树 — 小沈 2026-07-03 从list_directory拆分"""
    t0 = _time_mod.perf_counter()
    if max_depth < 1:
        max_depth = 1

    if not dir_path or not dir_path.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail="dir_path不能为空", hint="请提供目录路径", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={}, llm_data=llm_data)

    if sort_by not in ("name",):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name',当前值: '{sort_by}'", hint="sort_by只能为name", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={}, llm_data=llm_data)

    tree_result = await _get_directory_tree(dir_path=dir_path, max_depth=max_depth, include_hidden=include_hidden)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if "error_detail" in tree_result:
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=tree_result["error_detail"], hint="请检查目录路径是否正确", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data=tree_result, llm_data=llm_data)
    else:
        file_count = tree_result["statistics"]["file_count"]
        dir_count = tree_result["statistics"]["dir_count"]
        total = file_count + dir_count
        llm_data = _build_tree_llm_data("success", duration_ms, dir_path=dir_path, total=total, file_count=file_count, dir_count=dir_count, user_include_hidden=include_hidden, user_sort_by=sort_by)
        # ---- observation_formatter route -------------------------------------------
        # branch: #12 tree
        # trigger: "tree" in data and isinstance(data.get("tree"), dict)
        # handler: _format_tree(data) — 嵌套dict→可视化树形字符串
        # file:    observation_formatter.py:184-186
        # ------------------------------------------------------------------------------
        return build_success(data=tree_result, llm_data=llm_data)
