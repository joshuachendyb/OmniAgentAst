# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-04 - 小欧 - 新建: delete 工具专属差异安全判定(R3-R6), 设计文档第六章 6.2(v1.15) — 北京老陈驱动
# 2026-08-10 - 小欧 - ⑫多授权域(步骤1实施, 北京老陈驱动): 新增_get_allowed_roots=[项目根]+授权目录get_allowed_dirs()/_is_inside_any; R3-R6判定从单项目根扩展为多授权根, 授权目录内递归降级R4确认不再误拦R6
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1盲点二/四: SafetyResult 与 _get_project_root_safety 均迁 app/tools/security, import 同步更新 — 小欧 2026-08-12
# 2026-08-13 - 小欧 - 三堂会审修复#25: _get_allowed_roots 读取授权目录的 except pass 静默吞→logger.warning 留痕
#   (授权目录读取失败致删除判定根集缺失无任何日志, 排查无迹)
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

from app.tools.security.safety_result import SafetyResult  # A1盲点四 — 小欧 2026-08-12
from app.tools.security.path_safe_check import _get_project_root_safety  # A1盲点二 — 小欧 2026-08-12
from app.logger import logger  # #25: 授权目录丢失留痕 — 小欧 2026-08-13


def _as_bool(v: Any) -> bool:
    """布尔强转 — 防 LLM 原始参数 'false'/'true' 字符串陷阱: bool('false')==True 错误 — 小欧 2026-08-04"""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


_PASS = SafetyResult(blocked=False, requires_confirmation=False,
                     message="", safety_level="safe")          # 放行统一产物 — 小欧 2026-08-04


def _get_allowed_roots() -> list:
    """获取删除判定允许根列表 = [项目根] + 授权目录 — 小欧 2026-08-10 ⑫多授权域"""
    from app.config import get_config
    roots = [_get_project_root_safety()]
    try:
        for d in get_config().get_allowed_dirs():
            roots.append(Path(d).resolve())
    except Exception as e:
        # #25修复: 授权目录读取失败不再静默吞, 留warning日志(避免安全判定根集缺失无痕) — 小欧 2026-08-13
        logger.warning(f"[delete_safety] 读取授权目录失败, 授权根集不完整: {e}")
    return roots


def _is_inside_any(p: Path, roots: list) -> bool:
    """p 是否位于任一允许根内(含根自身) — 小欧 2026-08-10 ⑫"""
    for root in roots:
        if p == root or root in p.parents:
            return True
    return False


def check_delete_risk(params: dict) -> SafetyResult:
    """delete 专属差异判定(R3-R6) — 小欧 2026-08-04, 2026-08-10 ⑫多授权域(项目根+授权目录)

    恒返回 SafetyResult(从不用 None), 使调用侧可用 `delete_risk is not None`
    区分"是delete工具", R3 用 _PASS 表示免确认 —— 修复 v1.9 版本 R3=None
    导致 _get_needs_confirmation 落入原逻辑 needs_confirmation=True 的缺陷。
    R1/R2 由 _check_known_risks(validate_tool_path) 覆盖, 此处不重复。
    补D: 递归删除走 os.walk 时各子路径逐项判定, 任一越权即 R6。
    """
    path = str(params.get("path") or "").strip()
    recursive = _as_bool(params.get("recursive", False))       # 递归默认 False, 防字符串陷阱

    try:                                                        # 路径归一化
        p = Path(os.path.expanduser(path)).resolve()
    except Exception:
        return _PASS                                            # 路径异常→放行, 工具层validate会拦

    allowed_roots = _get_allowed_roots()                        # [项目根]+授权目录(⑫)
    inside_proj = _is_inside_any(p, allowed_roots)

    # --- R6 全部允许根外递归 → 拒 ---
    if (not inside_proj) and recursive:
        return SafetyResult(blocked=True, message=f"禁止删除项目根/授权目录外目录(递归): {path}", safety_level="dangerous")

    # --- R4 允许根内递归 → 确认 / R5 允许根外普通 → 确认 ---
    if (inside_proj and recursive) or (not inside_proj):
        return SafetyResult(requires_confirmation=True, blocked=False,
                            message=f"删除需确认: {path}", safety_level="destructive")

    # --- R3 允许根内普通 → 放行(免确认), 恒非None ---
    return _PASS


__all__ = ["_as_bool", "check_delete_risk", "_PASS", "_get_allowed_roots", "_is_inside_any"]