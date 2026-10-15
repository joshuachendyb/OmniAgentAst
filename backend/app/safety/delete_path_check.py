# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 删线独立文件。
#   自 path_safe_check.validate_path(:287-400) 拆出删线独有策略, 逐字搬迁不改逻辑:
#     删线特征 (:325-328): 命中禁区(system 与 non_system 一律) → 硬拦, **无授权分支**
#     删线白名单外 (:392-395): 与写线同, 查任务级授权
#   公共步骤(空路径/穿越/白名单匹配)交 path_check_common, 禁区分类仍调 _is_forbidden_path 并传 DELETE_MODE。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 文档[35] 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 文档[35] 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
"""
delete_path_check — 删操作路径检查(删线)

删线策略:
  一、命中禁区 → 一律硬拦, 无授权分支(system 与 non_system 同等待遇)
  二、白名单外 → 查任务级授权(与写线同)

公共步骤(空路径/穿越/白名单匹配)在 path_check_common, 禁区分类仍调
_is_forbidden_path 并传 DELETE_MODE, 本文件只放删线独有的策略分支。

删线之外还有一层更深的防线在工作区边界(R6: 禁止删除工作区外目录递归),
不在本模块 —— 那是 delete 工具专属差异层, 判的是"工作区边界"而非"路径权限",
职责不同故分属两个文件。

调用方:
  ① path_check_entry.validate_tool_path 按 action_kind=="delete" 调本模块
  ② delete_safety.check_delete_risk 经 SA3 双轨消费其结果

九格契约表(读/写/删 × 各类区域)见同包 path_safe_check 模块头 ——
本模块只负责本线实现, 契约表单一真源, 不在此重复维护(改一处三线皆知)。

小欧 2026-10-15
"""

from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.safety.path_safe_check import _is_forbidden_path
from app.safety.temp_auth import is_temp_authorized

DELETE_MODE = "delete"


def validate(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """删线路径检查 — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        命中禁区时 category 原样带回, 供调用方按 system/non_system 分流。
    """
    try:
        pre = common.check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 删线传 DELETE_MODE
        category, msg = _is_forbidden_path(file_path, DELETE_MODE)
        if category:
            return False, msg, category                          # 删线独有: 禁区一律硬拦, 无授权分支

        paths = common.resolve_allowed_paths(allowed_paths)
        if common.check_whitelist(file_path, paths):
            return True, None, None
        if is_temp_authorized(file_path):
            return True, None, None
        return False, f"路径 '{file_path}' 不在允许的操作范围内(仅允许:{', '.join(str(p) for p in paths[:5])}...)", None
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与 _is_forbidden_path 异常处理口径一致
        return False, f"路径验证失败: {str(e)}", "system"


__all__ = ["validate"]