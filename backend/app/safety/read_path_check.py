# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 读线独立文件。
#   自 path_safe_check.validate_path(:287-400) 拆出读线独有策略, 逐字搬迁不改逻辑:
#     读线特征一 (:321-322): 命中禁区 → 放行, category 原样带回给调用方做分流
#     读线特征二 (:387-391): 白名单外 → 放行
#   公共步骤(空路径/穿越/白名单匹配)交 path_check_common, 禁区分类仍调 _is_forbidden_path 并传 READ_MODE。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 文档[35] 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 文档[35] 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 北京老陈裁定 - 删白名单死分支: if 两支返回值一字不差, 判定零影响。
# 2026-10-15 北京老陈裁定 - validate 改名 validate_read: 三线同名, 经模块引用无法辨识线的语义。
"""
read_path_check — 读操作路径检查(读线)

读线策略(两条独有规则):
  一、命中禁区也放行 —— 系统目录/代码库根可读, 内容敏感性交 contentFilter 兜底
  二、白名单外也放行 —— 读不写盘, 无副作用

读线处处放行, 故【不做白名单匹配】(匹配了也不改变结果, 属无效计算)。
公共步骤(空路径/路径穿越)在 path_check_common, 禁区分类仍调
_is_forbidden_path 并传 READ_MODE, 本文件只放读线独有的策略分支。

调用方: path_check_entry.validate_tool_path 按 action_kind=="read" 调本模块。

九格契约表(读/写/删 × 各类区域)见同包 path_safe_check 模块头 ——
本模块只负责本线实现, 契约表单一真源, 不在此重复维护(改一处三线皆知)。

小欧 2026-10-15
"""

from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.safety.path_safe_check import _is_forbidden_path

READ_MODE = "read"


def validate_read(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """读线validate_read — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        读线只在"空路径/路径穿越"两种非法输入上返回 False, 其余一律 True。
        allowed_paths 形参保留但不使用: 读线处处放行, 白名单判定无影响(见头部裁定)。
    """
    try:
        pre = common.check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 读线传 READ_MODE, 系统目录在读线下判定为非禁区(放行)
        category, msg = _is_forbidden_path(file_path, READ_MODE)
        if category:
            return True, None, category          # 读线独有: 禁区放行, category 带回供调用方分流

        return True, None, None                  # 读线独有: 非禁区一律放行(含白名单外)
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与 _is_forbidden_path 异常处理口径一致;
        #   原 category=None → T2 当"白名单外非禁区→可授权请求" → 异常/恶意路径可被 grant_temp_auth 放行(安全漏洞)
        return False, f"路径验证失败: {str(e)}", "system"


__all__ = ["validate_read"]
