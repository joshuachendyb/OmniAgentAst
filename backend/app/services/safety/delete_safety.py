# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-04 - 小欧 - 新建: delete 工具专属差异安全判定(R3-R6), 设计文档第六章 6.2(v1.15) — 北京老陈驱动
"""
delete_safety — delete 工具专属安全检查(差异层)

职责: check_delete_risk 只判 R3-R6(项目根边界+递归差异), 恒返回 SafetyResult(R3→_PASS, 不用 None 表示放行)。
R1(系统盘/系统目录) 与 R2(磁盘根递归) 由 _check_known_risks → validate_tool_path → _is_forbidden_path 无条件覆盖,
此处不重复实现(DRY/SRP, 三堂会审)。

调用方: tool_safety_checker.check_before_execute 对 delete 工具一次性计算 delete_risk, 双轨消费:
        R6 blocked 入 _check_known_risks 无条件拦截, R3-R5 入 _get_needs_confirmation 确认分流。

小欧 2026-08-04
"""
import os
from pathlib import Path
from typing import Any

from app.services.safety.tool_safety_checker import SafetyResult
from app.services.safety.path_safe_check import _get_project_root_safety


def _as_bool(v: Any) -> bool:
    """布尔强转 — 防 LLM 原始参数 'false'/'true' 字符串陷阱: bool('false')==True 错误 — 小欧 2026-08-04"""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


_PASS = SafetyResult(blocked=False, requires_confirmation=False,
                     message="", safety_level="safe")          # 放行统一产物 — 小欧 2026-08-04


def check_delete_risk(params: dict) -> SafetyResult:
    """delete 专属差异判定(R3-R6) — 小欧 2026-08-04

    恒返回 SafetyResult(从不用 None), 使调用侧可用 `delete_risk is not None`
    区分"是delete工具", R3 用 _PASS 表示免确认 —— 修复 v1.9 版本 R3=None
    导致 _get_needs_confirmation 落入原逻辑 needs_confirmation=True 的缺陷。
    R1/R2 由 _check_known_risks(validate_tool_path) 覆盖, 此处不重复。
    """
    path = str(params.get("path") or "").strip()
    recursive = _as_bool(params.get("recursive", False))       # 递归默认 False, 防字符串陷阱

    try:                                                        # 路径归一化
        p = Path(os.path.expanduser(path)).resolve()
    except Exception:
        return _PASS                                            # 路径异常→放行, 工具层validate会拦

    proj_root = _get_project_root_safety()                      # 项目根(Safety层, 恒非None)
    inside_proj = (p == proj_root) or (proj_root in p.parents)

    # --- R6 项目根外递归 → 拒 ---
    if (not inside_proj) and recursive:
        return SafetyResult(blocked=True, message=f"禁止删除项目根外目录(递归): {path}", safety_level="dangerous")

    # --- R4 项目根内递归 → 确认 / R5 项目根外普通 → 确认 ---
    if (inside_proj and recursive) or (not inside_proj):
        return SafetyResult(requires_confirmation=True, blocked=False,
                            message=f"删除需确认: {path}", safety_level="destructive")

    # --- R3 项目根内普通 → 放行(免确认), 恒非None ---
    return _PASS


__all__ = ["_as_bool", "check_delete_risk", "_PASS"]