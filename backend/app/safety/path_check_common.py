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
# 2026-10-17 北京老陈裁定 - check_preconditions 迁至 app.utils.path_utils(空值与穿越判定归 tool 侧公用层), 本模块只余白名单判定; __all__ 与 safety/__init__ 同步取消该符号转出(禁 backward 再导出)。
# 2026-10-18 - 小欧 - [38]§12.2 落地: 新增工具级逐路径循环 check_tool_paths(下沉自 path_legality_router 内联循环),
#   三线工具级封装口(read/write/delete_permission 工具级口)共用此循环(DRY); 单路径判定以 judge 回调注入;
#   空值硬拦/内容型跳过/路径解析/异常 fail-closed 四件事集中于此。resolve_path_param 惰性导入(避免本模块↔dual 顶层环)。
"""
path_check_common — 读/写/删三条线共用的检查步骤

三线各自独立成文件(read_path_check / write_path_check / delete_path_check),
本模块只放它们**一字不差都要做**的步骤, 不含任何一条线独有的策略:

  check_whitelist        白名单前缀匹配   —— 三线同一套匹配规则(含盘根特例)
  resolve_allowed_paths  白名单取值       —— 三线同一句取值优先级
  check_tool_paths       工具级逐路径循环 —— 三线工具级封装口共用(judge 回调注入)

三线各自独有、由各自文件决定的部分(不在本模块):
  读线: 禁区放行 + 白名单外放行
  写线: system 硬拦 / non_system 查任务级授权
  删线: 禁区全硬拦、无授权分支
  三线共同调用 path_classify_category.classify_forbidden_path(禁区分类), 但传入各自的 mode

小欧 2026-10-15
"""

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.logger import logger
from app.safety.path_env import get_default_allowed_paths
from app.tools.tool_constants import PATH_PARAM_KEYS, CONTENT_PARAM_KEYS
from app.tools.tool_types import SafetyResult
from app.utils.path_utils import reject_reason_empty_path


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


def check_tool_paths(tool_name: str, params: Dict[str, Any],
                     judge: Callable[[str], SafetyResult]) -> SafetyResult:
    """三线共用: 遍历路径参数逐个判定, 首个越权即返回 — 小欧 2026-10-18

    read/write/delete 三条线的**工具级**封装口共用此循环(DRY), 只把"单路径判定"作为
    judge 回调注入; 空值硬拦 / 内容型跳过 / 路径解析 / 异常 fail-closed 四件事集中于此,
    各线不再重写(原 path_legality_router 内联循环, 2026-10-18 下沉到本模块)。
    """
    # 惰性导入: resolve_path_param 在 dual_path_check, 本模块被三线导入, 顶层导入会成环
    from app.safety.dual_path_check import resolve_path_param
    try:
        for key in PATH_PARAM_KEYS:
            if key not in params:
                continue                                # 真没传(见 precheck 同处裁定)
            value = params[key]
            if key in CONTENT_PARAM_KEYS and not isinstance(value, str):
                continue                                # data 内容型参数: 内联结构非路径
            _empty = reject_reason_empty_path(value)    # 空值真源在原子
            if _empty:
                return SafetyResult(blocked=True, severity="dangerous", message=_empty)
            if not isinstance(value, str):
                continue
            real_path = resolve_path_param(tool_name, key, value, params)
            result = judge(real_path)
            if result.blocked or result.requires_confirmation:
                return result
        return SafetyResult.pass_result()
    except Exception as e:
        # fail-closed: 兜底异常归 blocked(永不授权硬拦), 与三线各 except 口径全链一致
        return SafetyResult(blocked=True, severity="dangerous", message=f"路径安全检查异常: {e}")


__all__ = ["check_whitelist", "resolve_allowed_paths", "check_tool_paths"]
