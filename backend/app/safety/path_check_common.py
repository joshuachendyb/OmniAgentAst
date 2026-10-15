# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 抽自 path_safe_check.py 的三线公共步骤。
#   迁移 validate_path(:287-400) 中三线完全共用的部分, 逐字搬迁只改 import 路径, 业务逻辑一字不改:
#     ① 空路径判定(:311-315)          → check_preconditions
#     ② 路径穿越检测(:337-352, 16行)  → check_preconditions
#     ③ 白名单前缀匹配(:357-382, 26行)→ check_whitelist
#   新增 resolve_allowed_paths: 收敛 "allowed_paths 显式传入优先, 否则取默认白名单" 这一句,
#     原为 validate_path(:357) 内联单行, 三线各写一遍违反 DRY。
#   禁区分类(classify_forbidden_path)不在本模块: 它按 mode 决定读放行/写删拦, 三线传入的 mode 不同,
#     故由三线各自直接调用并传本线固定 mode(文档[35] v1.8 修订#1)。
# 2026-10-15 - 小欧 - 文档[35] P0-7/P0-8 修复(三堂会审, 均先实测复现再改):
#   P0-7 白名单单条坏值致整体崩: allowed_real 归一化原在 try 外, 实测传 [None] 抛 TypeError
#        冒泡至三线后全盘判 system。移入 try 并补 TypeError; 坏条目跳过=该条目不提供权限。
#   P0-8 白名单比对大小写敏感: 实测 E:\MyProject\... vs 白名单 E:\myproject 未命中,
#        用户在项目目录内却被要求授权。比对统一走小写(Windows-only 语义)。
"""
path_check_common — 读/写/删三条线共用的检查步骤

三线各自独立成文件(read_path_check / write_path_check / delete_path_check),
本模块只放它们**一字不差都要做**的步骤, 不含任何一条线独有的策略:

  check_preconditions    空路径 / 路径穿越 —— 三线都是硬拦, 无例外
  check_whitelist        白名单前缀匹配   —— 三线同一套匹配规则(含盘根特例)
  resolve_allowed_paths  白名单取值       —— 三线同一句取值优先级

三线各自独有、由各自文件决定的部分(不在本模块):
  读线: 禁区放行 + 白名单外放行
  写线: system 硬拦 / non_system 查任务级授权
  删线: 禁区全硬拦、无授权分支
  三线共同调用 path_guard.classify_forbidden_path(禁区分类), 但传入各自的 mode

小欧 2026-10-15
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

from app.logger import logger
from app.safety.path_env import get_default_allowed_paths


def check_preconditions(file_path: str) -> Optional[Tuple[bool, Optional[str], Optional[str]]]:
    """空路径 / 路径穿越判定 — 小欧 2026-10-15

    自 path_safe_check.validate_path(:311-315 + :337-352) 逐字迁出。

    Args:
        file_path: 待检查路径

    Returns:
        命中即返回 (False, msg, "system")；未命中返回 None，交各线继续。
        category 恒为 "system"(永不授权), 与 T2 硬拦口径一致。
    """
    # T2 回归修复(三堂会审复核发现, v1.45): 空路径是无效参数, 归入 category="system"(永不授权),
    #   原返回 category=None → T2 当"白名单外非禁区→可授权请求", 空路径从 blocked 退化为可授权(退化);
    #   与 test_bug_empty_path_not_validated 断言(空路径应 blocked)对齐 — 小欧 2026-08-10
    if not file_path or not file_path.strip():
        return False, "路径为空", "system"

    # 路径穿越拒绝: 包含..的路径直接拒绝 — 小欧 2026-06-25
    # T2 回归修复 (v1.45): 穿越路径归入 category="system"(永不授权) — 原返回 None → T2 当白名单外可授权,
    #   与 test_f5_03_path_traversal_blocked 断言(穿越应 blocked)对齐 — 小欧 2026-08-10
    try:
        # 检查原始路径的每个部分是否包含..
        path_parts = Path(file_path).parts
        if ".." in path_parts:
            return False, f"路径包含..,禁止路径穿越: {file_path}", "system"
        # 也检查规范化解析后的路径（处理绝对路径中的..）
        resolved = os.path.realpath(file_path)
        original_resolved = os.path.realpath(os.path.dirname(file_path))
        if not resolved.startswith(original_resolved) and file_path != resolved:
            return False, f"路径穿越检测: {file_path} 解析为 {resolved}", "system"
    except Exception as e:
        logger.warning(f"[path_check_common] 路径校验异常: {file_path}: {e}")
        return False, f"路径校验异常: {file_path}", "system"

    return None


def check_whitelist(file_path: str, allowed_paths: List[Path]) -> bool:
    """白名单前缀匹配 — 小欧 2026-10-15

    自 path_safe_check.validate_path(:357-382) 迁出。路径 realpath 化后, 与每个白名单根做
    parts 前缀比对; 白名单根为盘根(如 D:\\)时走盘根特例分支(整盘同盘即算命中)。
    比对统一走小写形式(Windows 路径不区分大小写)。

    Args:
        file_path: 待检查路径
        allowed_paths: 已解析的白名单根列表, 由 resolve_allowed_paths 取得

    Returns:
        命中任一白名单根返回 True; 全部未命中(含全部条目不可解析)返回 False。
    """
    real_path = Path(os.path.realpath(os.path.expanduser(file_path)))
    for allowed in allowed_paths:
        try:
            allowed_real = Path(os.path.realpath(allowed))
            real_parts = tuple(p.lower() for p in Path(real_path).parts)
            allowed_parts = tuple(p.lower() for p in Path(allowed_real).parts)

            if len(real_parts) >= len(allowed_parts):
                prefix_match = all(real_parts[i] == allowed_parts[i] for i in range(len(allowed_parts)))
                if not prefix_match:
                    continue

                if len(allowed_parts) == 1 and allowed_parts[0].endswith((":", ":\\", ":/")):
                    if str(real_path).lower() == str(allowed_real).lower() or real_parts[0] == allowed_parts[0]:
                        return True
                else:
                    # 2026-10-15 小欧 - P1-13: 此处原重复判 len 条件, 外层 if 已保证, 恒为真(死代码)。
                    return True
        except (ValueError, OSError, TypeError):
            # 坏条目(None/非路径对象)跳过=该条目不提供权限。TypeError 必须在内: realpath(None) 抛它。
            # 2026-10-15 小欧 - P3: 补 debug 日志(不用 warning: 每次路径检查都调, 会刷屏)。
            logger.debug(f"[path_check_common] 白名单条目无法解析, 已跳过: {allowed!r}")
            continue
    return False


def resolve_allowed_paths(allowed_paths: Optional[List[Path]]) -> List[Path]:
    """白名单取值: 显式传入优先, 否则取默认白名单 — 小欧 2026-10-15

    收敛自 path_safe_check.validate_path(:357) 的内联单行, 三线共用。
    默认白名单 = 主目录 + tmp + /var/tmp + 项目根 + 授权目录 + 会话工作区
    (由 path_env.get_default_allowed_paths 提供)。
    """
    return allowed_paths if allowed_paths is not None else get_default_allowed_paths()


__all__ = ["check_preconditions", "check_whitelist", "resolve_allowed_paths"]
