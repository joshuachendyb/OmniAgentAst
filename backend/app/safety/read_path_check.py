# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 读线独立文件。自 path_safe_check.validate_path(:287-400) 拆出读线独有策略, 逐字搬迁不改逻辑(读线特征一 :321-322 命中禁区→放行 category 原样带回; 读线特征二 :387-391 白名单外→放行); 公共步骤交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 READ_MODE。原 validate_path 及 mode 参数已删除(禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 - 删白名单死分支: if 两支返回值一字不差, 判定零影响。
# 2026-10-15 - validate 改名 validate_read: 三线同名, 经模块引用无法辨识线的语义。
# 2026-10-17 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path。
# 2026-10-17 - 小欧 - 基础封装: 新增 check_read_permission(path) 封装口, 三线统一返回 SafetyResult(签名按各线所需: 仅删线需 params.recursive), 供确认段统一消费。
# 2026-10-17 - 小欧 - 死参清理: 删死参 allowed_paths(validate_read) 与 params(check_read_permission, 方案A); 删死 import path_check_common(读线公共步骤已迁 app.utils.path_utils)。
# 2026-10-18 - 小欧 - 落地: 原单路径口 check_read_permission(path) 更名 read_permission(path)(供 dual/shell 复用);
#   新增工具级 check_read_permission(tool_name, params), 遍历参数经 common.check_tool_paths 逐条走 read_permission, 供 router 直调。
# 2026-10-18 - 小欧 - check_tool_paths 已删除: 单线工具路径键恒为 path(L2 已归一), 工具级口改为直接取 params["path"] 调 read_permission;
#   空值/穿越由 validate_read 自身拦截; 未传 key → 放行(与旧循环"真没传"口径一致)。
# 2026-10-18 - 小欧 - 随契约调整同步: 两个结果补 safety_level="path_auth"(读线唯一来源分类, 非法路径输入亦属路径授权范畴), 分类由本线直给而非上层反查文案; 原 severity 两处(dangerous/safe)分别与 blocked/needs_confirm 等价、属重复编码, 一并删; requires_confirmation 随字段改名。读线"处处放行、仅空值/穿越/异常硬拦"的核心策略零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): 上一条标的 path_auth 属**误标**并在此订正 ——
#   读线从不产生确认(无授权可给), 故不属确认命名空间; 硬拦归 BLOCK_PATH_INVALID, 放行不带标签。
#   读线"处处放行、仅空值/穿越/异常硬拦"的核心策略零变更。
# 2026-10-19 小欧 - 目录名单收口: 禁区判定改查 path_dir_lists 名单(classify_scope 取五档归属),
#   原 classify_forbidden_path 适配壳已随 path_classify_category.py 删除; 读线不查白名单(只判禁区)这一点不变。
# 2026-10-19 小欧 - 非法输入归属口径归一: 空路径/`..`穿越/异常三处返回的第三元素由旧 category 字面量
#   "system" 改为 SCOPE_FORBIDDEN_SYSTEM(读线判定用 `if not _ok`, 行为不变, 仅归属取值与写/删线一致)。
# 2026-10-19 小欧 - 去冗余: check_read_permission 删死参 tool_name(本口只按参数键判路径, 不用工具名);
#   router 调用点同步改单参。
# 2026-10-20 小欧 - validate_read 恒返回完整五档 scope(原非禁区返回 None, 上层复用归属只能判
#   "== 系统禁区"); 读线判定行为不变(五档全放行) — 小欧-2026-10-20
r"""read_path_check — 读操作路径检查(读线)
★r 前缀必需: 下方说明含 Windows 路径反斜杠(C:\Users 等), 无 r 会被当 \U \W 转义序列报错。

读线策略(2026-10-19 起, 单一真源 = path_dir_lists):
  一次 classify_scope 取五档归属, 再查 path_dir_lists.PERMISSION 的读格 —— **读线五档全放行**。
  读线**不查白名单**: 白名单外的路径读操作照常放行(读不产生不可逆后果)。
  唯一会拒绝的是**非法输入**: 空路径 / `..` 穿越 / 格式化失败 / 判定异常, 一律 fail-closed。

| 归属                | 读 |
|---------------------|-----|
| 禁区·系统           | 放行 |
| 禁区·非系统         | 放行 |
| 白名单·自身         | 放行 |
| 白名单·下级         | 放行 |
| 白名单外            | 放行 |

  非法输入(空路径 / `..` 穿越 / 异常) → 拒绝(BLOCK_PATH_INVALID)。

读线与写/删线的差异: 读不产生不可逆后果, 故读线对所有目录档位一律放行, 只对非法输入拒绝。
  写/删两线的档位差异见 path_dir_lists.PERMISSION —— 契约表单一真源, 本模块不重复维护。

小欧 2026-10-15 建 / 2026-10-19 小欧 重写
"""

from typing import Any, Dict, Optional, Tuple

from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17  本函数自 path_check_common 迁 path_utils
from app.safety.path_dir_lists import (  # 2026-10-19 小欧 - 目录名单收口: 读线禁区分档改查名单
    classify_path,
    SCOPE_FORBIDDEN_SYSTEM,
)
from app.safety.safety_result import SafetyLevel, SafetyResult   # 契约: 安全层单源

READ_MODE = "read"


def validate_read(file_path: str) -> Tuple[bool, Optional[str], str]:
    """读线validate_read — 小欧 2026-10-15 / 2026-10-20

    Returns:
        (is_valid, error_message, scope), scope 恒为五档之一(非禁区不再返回 None)
        读线只在"空路径/路径穿越/异常"三类非法输入上返回 False(归 SCOPE_FORBIDDEN_SYSTEM), 其余一律 True。

    2026-10-20 小欧 - 恒返回完整 scope, 供上层复用归属(dual/shell 仍只判 SCOPE_FORBIDDEN_SYSTEM)。
    """
    try:
        _reason = reject_reason_empty_path(file_path) or check_preconditions(file_path)  # 空值真源在原子
        if _reason:
            # 非法输入一律归系统禁区: 判不出是否禁区 → 不放行(读线本无授权, 但归属口径与写/删线一致)
            return False, _reason, SCOPE_FORBIDDEN_SYSTEM

        # 禁区分类: 2026-10-19 小欧 - 目录名单收口: 改查名单, category 适配壳已删, 直接取 scope
        scope, _rule = classify_path(file_path)
        return True, None, scope                     # 读线独有: 五档全放行, 完整归属带回供调用方分流
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与写/删线异常处理口径一致;
        #   原 category=None → T2 当"白名单外非禁区→可授权请求" → 异常/恶意路径可被 grant_temp_auth 放行(安全漏洞)
        return False, f"路径验证失败: {str(e)}", SCOPE_FORBIDDEN_SYSTEM


def read_permission(path: str) -> SafetyResult:
    """读线单路径权限口 — 供 dual_path_check / shell_path_check 复用 — 小欧 2026-10-18

    读线处处放行(禁区放行 + 白名单外放行), 仅"空路径 / 路径穿越 / 异常"三类非法输入硬拦。
    读线**从不产生确认**(无授权可给), 故不属确认命名空间; 硬拦归 block_path_invalid,
    放行不带标签。原 safety_level="path_auth" 是误标 —— 把"放行"与"硬拦"都叫成"需授权"。
    """
    _ok, _msg, _category = validate_read(path)
    if not _ok:
        return SafetyResult(blocked=True, message=_msg, safety_level=SafetyLevel.BLOCK_PATH_INVALID)
    return SafetyResult(blocked=False, needs_confirm=False, message="")


def check_read_permission(params: Dict[str, Any]) -> SafetyResult:
    """读线工具级权限口 — 供 path_legality_router [3] 直调 — 小欧 2026-10-18

    2026-10-19 小欧 - 删死参 tool_name: 本口只按参数键判路径, 不用工具名。
    单线工具一调用只有一条路径, 键恒为 path(L2 已归一), 直接走 read_permission
    (读线处处放行, 仅空值/穿越/异常硬拦 —— 由 validate_read 自身判定)。
    """
    if "path" not in params:
        return SafetyResult.pass_result()
    return read_permission(params["path"])


__all__ = ["validate_read", "read_permission", "check_read_permission"]
