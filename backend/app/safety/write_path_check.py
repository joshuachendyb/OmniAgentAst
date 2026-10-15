# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 写线独立文件。
#   自 path_safe_check.validate_path(:287-400) 拆出写线独有策略, 逐字搬迁不改逻辑:
#     写线特征一 (:323-324): 命中 system 禁区 → 硬拦, 永不授权
#     写线特征二 (:325-333): 命中 non_system 禁区(代码库根/受保护根) → 查任务级授权, 无授权则拦
#     写线特征三 (:392-395): 白名单外 → 查任务级授权, 无授权则拦
#   公共步骤(空路径/穿越/白名单匹配)交 path_check_common, 禁区分类仍调 _is_forbidden_path 并传 WRITE_MODE。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 文档[35] 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 文档[35] 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
"""
write_path_check — 写操作路径检查(写线)

写线策略:
  一、命中 system 禁区 → 硬拦, 永不授权(磁盘根/系统敏感文件目录/系统保护目录)
  二、命中 non_system 禁区(代码库根/受保护根) → 查任务级授权, 已授权放行, 未授权拦
  三、白名单外 → 查任务级授权, 已授权放行, 未授权拦

公共步骤(空路径/穿越/白名单匹配)在 path_check_common, 禁区分类仍调
_is_forbidden_path 并传 WRITE_MODE, 本文件只放写线独有的策略分支。

调用方: path_check_entry.validate_tool_path 按 action_kind 选线; 未声明动作类型的
工具(fail-closed 默认)走本模块。

九格契约表(读/写/删 × 各类区域)见同包 path_safe_check 模块头 ——
本模块只负责本线实现, 契约表单一真源, 不在此重复维护(改一处三线皆知)。

小欧 2026-10-15
"""

from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.safety.path_safe_check import _is_forbidden_path
from app.safety.temp_auth import is_temp_authorized

WRITE_MODE = "write"


def validate(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """写线路径检查 — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        category=None 表示"白名单外非禁区", 交调用方按策略弹授权确认。
    """
    try:
        pre = common.check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 写线传 WRITE_MODE, 系统保护目录在写线下判定为禁区
        category, msg = _is_forbidden_path(file_path, WRITE_MODE)
        if category:
            if category == "system":
                return False, msg, "system"                       # 写线独有: system 硬拦永不授权
            if is_temp_authorized(file_path):
                return True, None, "non_system"
            return False, msg, "non_system"                       # non_system 写可任务级授权

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