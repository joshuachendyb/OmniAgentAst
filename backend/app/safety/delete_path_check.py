# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 删线独立文件。自 path_safe_check.validate_path(:287-400) 拆出删线独有策略, 逐字搬迁不改逻辑(删线特征 :325-328 命中禁区 system 与 non_system 一律硬拦, **无授权分支**; 白名单外 :392-395 与写线同, 查任务级授权); 公共步骤交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 DELETE_MODE。原 validate_path 及 mode 参数已删除(禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 北京老陈裁定 - validate 改名 validate_delete: 三线同名, 经模块引用无法辨识线的语义。
# 2026-10-17 北京老陈裁定 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path
# 2026-10-17 北京老陈裁定(裁定三) - 删线判定集中化: 自 delete_safety.py 逐字迁入 check_delete_risk(R3-R6), 并收归 guard_forbidden_delete(A族系统目录/磁盘根 + 代码目录 + 删根硬底线); 判据只调 path_classify_category 单源, 本层不持名单。tool 层 path_utils.check_path_five_level 第⑤级另持一份(同口径)不动, delete_safety.py 随之删除。 — 小欧 2026-10-17
# 2026-10-17 - 小欧 - 新增唯一封装口 check_delete_permission(path, params): ①guard_forbidden_delete → ②validate_delete(R1/R2) → ③check_delete_risk(R3-R6) 串链, 统一返 SafetyResult。三函数原功能全保留; validate_delete 亦供 path_legality_router 按线分派时调用。消费方: path_tool_safety_checker / shell_path_check / dual_path_check(三者纯调用, 判定全在本口); path_utils 第⑤级改调 guard_forbidden_delete。
r"""delete_path_check — 删操作路径检查(删线)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

删线策略:
  一、命中禁区 → 一律硬拦, 无授权分支(system 与 non_system 同等待遇)
  二、白名单外 → 查任务级授权(与写线同)

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块 validate_delete 只返回「放行/拒绝」两态(实测 白名单内直接放行, 无确认分支);
  表里的"确认"(弹窗授权)发生在**调用方** path_tool_safety_checker, 白名单内的"确认(根外递归, 来自 R6 层)"
  更来自本文件 **check_delete_risk 的 R6 工作区边界层**(2026-10-17 自 delete_safety 迁入)。
  → 按本表核对本文件代码时, "确认"格对不上是**正常的**, 那是上层行为。

| 区域                                       | category   | 读   | 写            | 删           |
|--------------------------------------------|------------|------|---------------|--------------|
| 空路径 / 含 `..` 路径穿越(非法输入)         | —          | 拒绝 | 拒绝          | 拒绝         |
| 磁盘根(任意盘符)                           | system     | 放行 | 拒绝          | 拒绝         |
| 系统敏感文件(config\SAM/SECURITY/SOFTWARE 等)| system    | 放行 | 拒绝          | 拒绝         |
| 系统目录(Windows/ProgramFiles/ProgramData/Boot/WinSxS) | system | 放行 | 拒绝 | 拒绝         |
| 代码目录 —— 自身及内部所有子级             | non_system | 放行 | 确认(任务级)  | 拒绝         |
| 授权目录 —— 自身及其上级祖先               | non_system | 放行 | 确认(任务级)  | 拒绝         |
| 白名单内(path_env.get_default_allowed_paths 动态取值) | None | 放行 | 放行 | 确认(根外递归, 来自 R6 层) |
| 白名单外普通路径                           | None       | 放行 | 确认(临时授权)| 确认         |
| 异常/恶意路径                              | system     | 拒绝 | 拒绝          | 拒绝         |

两个 non_system 类别的正式定义(勿凭字面猜):
  · 代码目录 = get_code_root()       判**自身 + 内部所有子级**; **父级不拦**
  · 授权目录 = get_allowed_roots()   判**自身 + 上级祖先**; **内部不拦**
               = 用户项目根 + **授权目录** + 会话工作区(session_workspace_paths) 三个来源

★删线比写线严: 两个 non_system 类(代码目录/授权目录)对删**一律硬拦不授权**(抹除不可逆)。
★但白名单外**不是**直接拒绝 —— 经任务级临时授权后**放行**(见 validate_delete 末段 is_temp_authorized);
  "确认"那一步在调用方, 不在本模块。
★本表是禁区分类的结果说明, 规则改动须同步本表, 勿只改表。

公共步骤(空路径/穿越/白名单匹配)在 path_check_common, 禁区分类仍调
classify_forbidden_path 并传 DELETE_MODE, 本文件只放删线独有的策略分支。

删线之外还有一层更深的防线在工作区边界(R3-R6), 由本模块 check_delete_risk 承担
(2026-10-17 自 delete_safety 迁入)—— 那是 delete 工具专属差异层, 判的是"工作区边界"
而非"路径权限"; 本文件现职责三分: validate_delete(R1/R2) / check_delete_risk(R3-R6) / guard_forbidden_delete(A族+删根硬底线)。



九格契约表(读/写/删 × 各类区域)见同包 path_classify_category 模块头 ——
本模块只负责本线实现, 契约表单一真源, 不在此重复维护(改一处三线皆知)。

小欧 2026-10-15
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17 北京老陈裁定: 本函数自 path_check_common 迁 path_utils
from app.safety.path_classify_category import (
    classify_forbidden_path,
    is_allowed_root_itself,
    is_code_root_path,
    is_disk_root,
    is_system_protected_path,
)
from app.safety.temp_auth import is_temp_authorized
from app.session_workspace import session_workspace_paths
from app.tools.tool_types import SafetyResult
from app.utils.path_utils import get_allowed_roots
from app.logger import logger

DELETE_MODE = "delete"


def validate_delete(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """删线validate_delete — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        命中禁区时 category 原样带回, 供调用方按 system/non_system 分流。
    """
    try:
        _empty = reject_reason_empty_path(file_path)   # 空值真源在原子, 本线不重复实现
        if _empty:
            return False, _empty, "system"
        pre = check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 删线传 DELETE_MODE
        category, msg = classify_forbidden_path(file_path, DELETE_MODE)
        if category:
            return False, msg, category                          # 删线独有: 禁区一律硬拦, 无授权分支

        paths = common.resolve_allowed_paths(allowed_paths)
        if common.check_whitelist(file_path, paths):
            return True, None, None
        if is_temp_authorized(file_path):
            return True, None, None
        return False, f"路径 '{file_path}' 不在允许的操作范围内(仅允许:{', '.join(str(p) for p in paths[:5])}...)", None
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与 classify_forbidden_path 异常处理口径一致
        return False, f"路径验证失败: {str(e)}", "system"


def check_delete_risk(params: dict) -> SafetyResult:
    """delete 专属差异判定(R3-R6) — 由 delete_safety 迁入 — 小欧 2026-10-17

    恒返回 SafetyResult(从不用 None), 使调用侧可用 `delete_risk is not None`
    区分"是delete工具", R3 直接内联构造放行产物。
    R1/R2 由 _check_known_risks(check_tool_path_permission) 覆盖, 此处不重复。
    补D: 递归删除走 os.walk 时各子路径逐项判定, 任一越权即 R6。
    由总闸内调, R1/R2 回路径层覆盖 — 小欧-2026-10-14
    函数体逐字复制 delete_safety.check_delete_risk, 逻辑一字不改, 仅改日志前缀。
    """
    path = str(params.get("path") or "").strip()
    _rv = params.get("recursive", False)
    recursive = (str(_rv).strip().lower() in ("1", "true", "yes", "on"))  # 防 LLM 传字符串 'false' 被 bool() 当真

    try:                                                        # 路径归一化
        p = Path(os.path.expanduser(path)).resolve()
    except Exception as e:
        # fail-closed: 归一化失败即判 blocked, 宁可拒不可放(不依赖下一道防线)。
        logger.warning(f"[delete_path_check] 路径归一化失败, 按拒绝处理: {path!r} ({e})")
        return SafetyResult(blocked=True, requires_confirmation=False,
                            message=f"删除路径非法: {path}", severity="dangerous")

    try:
        allowed_roots = get_allowed_roots(session_workspace_paths())  # 单源: 项目根+授权目录+会话目录(⑫)
    except Exception as e:
        # fail-closed: 根集读不出时若继续判, inside 恒 False → 全部路径误判区外(R5/R6), 语义翻转
        logger.warning(f"[delete_path_check] 允许根读取失败, 按拒绝处理: {e}")
        return SafetyResult(blocked=True, requires_confirmation=False,
                            message=f"删除安全判定不可用(根集读取失败): {e}", severity="dangerous")

    inside_proj = any(p == root or root in p.parents for root in allowed_roots)

    # --- R6 全部允许根外递归 → 拒 ---
    if (not inside_proj) and recursive:
        return SafetyResult(blocked=True, message=f"禁止删除工作区外目录: {path}", severity="dangerous")

    # --- R4 允许根内递归 → 确认 / R5 允许根外普通 → 确认 ---
    if (inside_proj and recursive) or (not inside_proj):
        return SafetyResult(requires_confirmation=True, blocked=False,
                            message=f"删除需确认: {path}", severity="risk")

    # --- R3 允许根内普通 → 放行(免确认), 恒非None ---
    return SafetyResult(blocked=False, requires_confirmation=False,
                        message="", severity="safe")


def guard_forbidden_delete(file_path: str) -> Optional[str]:
    """删除硬底线: 命中禁区返回禁止原因, 允许删除返回 None — 系统层持一份 — 小欧 2026-10-17

    判据全部走 path_classify_category 单源, 本层不持名单; 与 tool 层
    path_utils.check_path_five_level 第⑤级同口径(各持一份调用壳, 判据同源)。
    """
    try:
        Path(file_path).expanduser().resolve()      # 归一化探针: 解析失败即 fail-closed
    except Exception as e:
        return f"安全校验: 路径解析失败({e})"
    if os.name == "nt" and is_system_protected_path(file_path, "delete"):
        return f"禁止删除系统目录: {file_path}"
    if is_disk_root(file_path):
        return f"禁止删除磁盘根目录: {file_path}"
    if is_code_root_path(file_path):
        return f"禁止删除代码目录(含其内部子级): {file_path}"
    _hit = is_allowed_root_itself(file_path)
    if _hit == "allowed_root_itself":
        return f"禁止删除项目根/授权根目录: {file_path}"
    if _hit == "allowed_root_ancestor":
        return f"禁止删除项目根/授权根上级目录: {file_path}"
    return None


def check_delete_permission(path: str, params: Optional[dict] = None) -> SafetyResult:
    """delete 权限识别(唯一封装口) — 小欧 2026-10-17

    把三件事有机串成一条链, 统一返回 SafetyResult:
      ① guard_forbidden_delete — A族(系统目录/磁盘根/代码目录/允许根本身+上级) → 命中即拒绝
      ② validate_delete      — R1/R2(空值/穿越/禁区分类/白名单/临时授权) → 命中禁区即拒绝
      ③ check_delete_risk    — R3-R6(区外递归→拒 / 根内递归→确认 / 区外→确认 / 根内普通→放行)
    三函数原功能全部保留, 命中哪条即出对应的 拒绝/要确认/放行。
    白名单外(② 返 category=None)不在此硬拦, 交 ③ 定 拒绝/确认。
    消费方: path_tool_safety_checker(删工具) / shell_path_check(删源) / dual_path_check(删除动作)。
    """
    # ① A族/删根硬底线
    _guard = guard_forbidden_delete(path)
    if _guard:
        return SafetyResult(blocked=True, message=_guard, severity="dangerous")
    # ② R1/R2 路径禁区(系统/代码目录/允许根本身 → 硬拦; 白名单外 → 交 ③)
    _ok, _msg, _category = validate_delete(path)
    if not _ok and _category:
        return SafetyResult(blocked=True, message=_msg, severity="dangerous")
    # ③ R3-R6 工作区边界
    _params = dict(params or {})
    _params.setdefault("path", path)
    return check_delete_risk(_params)


__all__ = ["validate_delete", "check_delete_risk", "guard_forbidden_delete", "check_delete_permission"]
