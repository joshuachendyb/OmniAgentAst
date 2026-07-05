# -*- coding: utf-8 -*-
"""
F5b: tree — 列出目录树

从list_directory.py拆分而来 — 小沈 2026-07-03
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
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger


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


async def _get_directory_tree(
    dir_path: str, max_depth: int = 10,
    include_hidden: bool = False, sort_by: str = "name",
) -> Dict[str, Any]:
    """获取目录树原始数据 — 小欧 2026-06-22 — 小健 2026-06-22 删除helper计时 — 小欧 2026-06-24 修复include_hidden和sort_by"""
    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在+是目录 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.LIST_DIR, dir_path)
    if not is_valid:
        return {"error_detail": err, "params": {"dir_path": dir_path}}

    path = Path(dir_path)

    def _count_tree_fs(root: Path) -> Tuple[int, int, int]:
        fc = dc = ts = 0
        try:
            for entry in os.scandir(root):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        dc += 1
                        sub_f, sub_d, sub_s = _count_tree_fs(Path(entry.path))
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

    def _sort_items(items, sort_by_param):
        """排序目录项 - 小沈 2026-07-01"""
        if sort_by_param == "mtime":
            def _get_mtime(p):
                try:
                    return p.stat().st_mtime
                except OSError:
                    return 0
            return sorted(items, key=lambda x: (-_get_mtime(x), x.name.lower()))
        # name/size均回退按名称排序(tree只列目录,size无意义)
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
            st = current_path.stat()
        except OSError:
            return None
        node: Dict[str, Any] = {
            "name": current_path.name,
            "path": str(current_path.absolute()),
            "type": "directory",
            "size": None,
            "mtime": st.st_mtime,
        }
        children: list = []
        try:
            items = [item for item in current_path.iterdir() if item.is_dir()]
            if not include_hidden:
                items = [item for item in items if not item.name.startswith('.')]
            for item in _sort_items(items, sort_by):
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
) -> Dict[str, Any]:
    """tree的llm_data构建函数 — 小沈 2026-07-03 — 小沈 2026-07-05 新增hint参数"""
    _act_params = {"dir_path": dir_path}
    if user_include_hidden is not None:
        _act_params["include_hidden"] = user_include_hidden
    if user_sort_by:
        _act_params["sort_by"] = user_sort_by
    if exec_code == "error":
        return {
            "summary": f"列出目录树失败: {dir_path}",
            "action": {"tool": "tree", "tool_zh": "列出目录树", "target": dir_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "列出目录树失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": hint if hint else "请检查目录路径和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"列出目录树成功: {dir_path} ({total}项)",
        "action": {"tool": "tree", "tool_zh": "列出目录树", "target": dir_path, "params": _act_params},
        "status": {"exec_code": "success", "message": "列出目录树成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"total": {"value": total, "text": f"{total}项"}},
    }


async def tree(
    dir_path: str,
    include_hidden: bool = False,
    sort_by: str = "name",
) -> Dict[str, Any]:
    """列出目录树 — 小沈 2026-07-03 从list_directory拆分"""
    t0 = _time_mod.perf_counter()
    max_depth = 10

    if not dir_path or not dir_path.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail="dir_path不能为空", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={"error_detail": "dir_path不能为空", "params": {"dir_path": dir_path}}, llm_data=llm_data)

    if sort_by not in ("name", "mtime"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name'/'mtime',当前值: '{sort_by}'", user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data={"error_detail": f"sort_by只支持name/mtime", "params": {"sort_by": sort_by}}, llm_data=llm_data)

    tree_result = await _get_directory_tree(dir_path=dir_path, max_depth=max_depth, include_hidden=include_hidden, sort_by=sort_by)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if "error_detail" in tree_result:
        llm_data = _build_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=tree_result["error_detail"], user_include_hidden=include_hidden, user_sort_by=sort_by)
        return build_error(data=tree_result, llm_data=llm_data)
    else:
        total = tree_result["statistics"]["file_count"] + tree_result["statistics"]["dir_count"]
        llm_data = _build_tree_llm_data("success", duration_ms, dir_path=dir_path, total=total, user_include_hidden=include_hidden, user_sort_by=sort_by)
        # ---- observation_formatter route -------------------------------------------
        # branch: #12 tree
        # trigger: "tree" in data and isinstance(data.get("tree"), dict)
        # handler: _format_tree(data) — 嵌套dict→可视化树形字符串
        # file:    observation_formatter.py:184-186
        # ------------------------------------------------------------------------------
        return build_success(data=tree_result, llm_data=llm_data)
