# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 删线独立文件。自 path_safe_check.validate_path(:287-400) 拆出删线独有策略, 逐字搬迁不改逻辑(删线特征 :325-328 命中禁区 system 与 non_system 一律硬拦, **无授权分支**; 白名单外 :392-395 与写线同, 查任务级授权); 公共步骤交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 DELETE_MODE。原 validate_path 及 mode 参数已删除(禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 小欧 - validate 改名 validate_delete: 三线同名, 经模块引用无法辨识线的语义。
# 2026-10-17 小欧 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path
# 2026-10-17 小欧 - 删线判定集中化: 自 delete_safety.py 逐字迁入 check_delete_risk(R3-R6), 并收归 guard_forbidden_delete(A族系统目录/磁盘根 + 代码目录 + 删根硬底线); 判据只调 path_classify_category 单源, 本层不持名单。tool 层 path_utils.check_path_five_level 第级另持一份(同口径)不动, delete_safety.py 随之删除。 小欧 2026-10-17
# 2026-10-17 - 小欧 - 新增唯一封装口 check_delete_permission(path, params): guard_forbidden_delete → validate_delete(R1/R2) → check_delete_risk(R3-R6) 串链, 统一返 SafetyResult。三函数原功能全保留; validate_delete 亦供 path_legality_router 按线分派时调用。消费方: path_tool_safety_checker / shell_path_check / dual_path_check(三者纯调用, 判定全在本口); path_utils 第级改调 guard_forbidden_delete。
# 2026-10-18 - 小欧 - 落地(字面9步): 原单路径口 check_delete_permission(path, params) 更名 delete_permission(path, params)(供 dual/shell 复用);
#   新增工具级 check_delete_permission(tool_name, params), 遍历参数经 common.check_tool_paths 逐条走 delete_permission, 供 router [6] 直调。
# 2026-10-18 - 小欧 - check_tool_paths 已删除: 单线删工具路径键恒为 path(L2 已归一), 工具级口直接取 params["path"]
#   调 delete_permission; 未传 key → 放行, 空值/穿越/禁区由 delete_permission 自身判定。
# 2026-10-18 - 小欧 - 随契约调整同步: 七处结果补 safety_level 问题来源分类 —— 工作区边界判定与 R3~R6 四档归 tool_delete, 删除硬底线(系统目录/磁盘根/代码目录/允许根本身与上级)与 validate_delete 禁区归 forbidden_zone, 分类由本线直给而非上层反查文案; 原 severity 七处取值分别与 blocked/needs_confirm 等价、属重复编码, 一并删; requires_confirmation 随字段改名四处。R1~R6 判定分支与放行口径零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): R6 根集外递归硬拦归 PATH_FORBIDDEN(同属路径策略硬拦, 非命令层问题);
#   R4 根内递归确认归 DELETE_RECURSIVE、R5 根集外确认归 DELETE_OUT_OF_SCOPE —— 上一条标 tool_delete 时 R4/R5 同标签, 前端无法区分;
#   格式化失败/根集读取失败两处 fail-closed 归 BLOCK_PATH_INVALID; A族硬底线与 validate_delete 禁区硬拦归 PATH_FORBIDDEN;
#   R3 放行不再带标签(无确认无拦截, 无分类可言)。R3-R6 判定分支与放行口径零变更。
# 2026-10-18 - 小欧 - R5 补 auth_path=path(缺陷修复): 原 R5 只给 needs_confirm 不给 auth_path, 而 safety_gate 确认后凭 auth_path
#   调 grant_temp_auth 落地临时授权 —— 缺它则本分支是死路: 弹窗承诺"申请临时授权", 用户确认后无授权落地,
#   delete 工具内 validate_delete 仍按白名单拒绝, 操作照样失败(承诺与结果不符)。与写线同文案同给 auth_path。
# 2026-10-18 - 小欧 - 文案术语对齐(get_allowed_roots / is_system_protected_path 原文): 统一"允许根集(项目根/授权目录/会话工作区)"
#   与"系统保护目录", 删自造的"工作区""允许的操作范围""受保护区域""允许根目录"四种命名。纯文案, 判定零变更。
# 2026-10-18 小欧 - R4/R5 文案改分行(做什么/对什么/原因/范围/时效), 原为一句话堆砌, 弹窗难读。判定零变更。
# 2026-10-19 小欧 - 目录名单收口: 三处取值全部改读 path_dir_lists 名单(validate_delete / check_delete_risk /
#   guard_forbidden_delete); 原四个判据函数与 classify_forbidden_path 适配壳已随 path_classify_category.py 删除;
#   判定改为"一次 classify_scope 取五档归属 + 查 path_dir_lists.PERMISSION 权限矩阵", 本文件不再持任何名单;
#   delete_permission 去掉与 check_delete_risk 重复的 validate_delete 一步(归属判定已收口到 check_delete_risk)。
# 2026-10-19 小欧 - 修复删线 `..`穿越回归 + 死代码清理: 非法输入(空值/`..`穿越)判定补回 check_delete_risk 入口
#   (原由 validate_delete 承担, 删该步后失效 → `..`被当"白名单外确认"而非硬拦); validate_delete 全库零调用,
#   连同其导出与 import 一并删除; check_delete_risk 格式化死变量 p 随之清理, 两处 fail-closed 兜底合一。
# 2026-10-19 小欧 - 去冗余: delete_permission 原先调 guard_forbidden_delete 再调 check_delete_risk,
#   两者同走 classify_path(每次删两次 realpath)且禁区结论一致(矩阵删格即 DENY)—— guard 一步移除,
#   禁区拦截由 check_delete_risk 单点承担; guard_forbidden_delete 保留为删工具执行层自持底线。
r"""delete_path_check — 删操作路径检查(删线)
★r 前缀必需: 下方说明含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

删线判定(2026-10-19 起, 单一真源 = path_dir_lists):
  一次 classify_scope 取五档归属(禁区·系统 / 禁区·非系统 / 白名单·自身 / 白名单·下级 / 白名单外),
  再查 path_dir_lists.PERMISSION 权限矩阵拿本线两格(普通删 / 递归删), 本文件不含任何名单字面量。

| 归属                 | 删(普通) | 删(递归) |
|----------------------|----------|----------|
| 禁区·系统            | 拒绝     | 拒绝     |
| 禁区·非系统          | 拒绝     | 拒绝     |
| 白名单·自身          | 拒绝     | 拒绝     |
| 白名单·下级          | 放行     | 放行     |
| 白名单外             | 确认     | 拒绝     |

  · 确认 = needs_confirm + auth_path, 由调用方(safety_gate)落临时授权; 拒绝 = blocked(PATH_FORBIDDEN)。
  · 非法输入(空路径 / `..` 穿越 / 格式化失败)一律 fail-closed 拒绝, 归 BLOCK_PATH_INVALID。
  · 异常路径归 SCOPE_FORBIDDEN_SYSTEM, 与读/写线口径一致(判不出是否禁区 → 不放行)。

本文件职责二分:
  check_delete_risk      — 非法输入 fail-closed + 按 params 里的 recursive 查矩阵, 出 拒绝/确认/放行 三档
  guard_forbidden_delete — 删工具执行层自保(防绕过安全线直调工具)

契约表(读/写/删/递归删 × 五档)见 path_dir_lists.PERMISSION —— 单一真源, 本模块不重复维护。

小欧 2026-10-15 建 / 2026-10-19 小欧 重写
"""

from typing import Any, Dict, Optional

from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17 小欧: 公共步骤从 path_check_common 迁 path_utils
from app.safety.path_dir_lists import (  # 2026-10-19 小欧 - 目录名单收口: 取值全部改读名单
    classify_path,
    permission_of,
    SCOPE_TEXT,
    SCOPE_FORBIDDEN_SYSTEM,
    SCOPE_FORBIDDEN_NON_SYSTEM,
    LINE_DELETE,
    LINE_DELETE_RECURSIVE,
    PASS,
    DENY,
)
from app.safety.safety_result import SafetyLevel, SafetyResult
from app.logger import logger

DELETE_MODE = "delete"


def check_delete_risk(params: dict) -> SafetyResult:
    """delete 专属差异判定(四档) — 小欧 2026-10-19 目录名单收口: 改查权限矩阵

    恒返回 SafetyResult(从不用 None), 使调用侧可用 `delete_risk is not None`
    区分"是delete工具"。
    非法输入(空值/`..`穿越)在此 fail-closed 拒绝, 归 BLOCK_PATH_INVALID。
    四档(读/写/删/递归删的"删"两格)全部由 path_dir_lists.PERMISSION 单一真源决定:

        禁区·系统/非系统   → 删拒绝 / 递归删拒绝
        白名单·自身        → 删拒绝(自身本就不该可删) / 递归删拒绝
        白名单·下级        → 放行 / 放行(递归也放行)
        白名单外          → 确认+临时授权 / 递归删拒绝
    """
    path = str(params.get("path") or "").strip()
    _rv = params.get("recursive", False)
    recursive = (str(_rv).strip().lower() in ("1", "true", "yes", "on"))  # 防 LLM 传字符串 'false' 被 bool() 当真

    # 非法输入(空路径 / `..` 穿越) fail-closed 拒绝 —— 判不出是否禁区 → 不放行
    _reason = reject_reason_empty_path(path) or check_preconditions(path)
    if _reason:
        return SafetyResult(blocked=True, needs_confirm=False,
                            message=f"删除路径非法: {_reason}",
                            safety_level=SafetyLevel.BLOCK_PATH_INVALID)

    try:
        scope, _ = classify_path(path)
    except Exception as e:
        # fail-closed: 格式化异常或名单读不出时若继续判, outside 恒成立 → 全部路径误判范围外, 语义翻转
        logger.warning(f"[delete_path_check] 删除安全判定不可用, 按拒绝处理: {path!r} ({e})")
        return SafetyResult(blocked=True, needs_confirm=False,
                            message=f"删除安全判定不可用: {e}", safety_level=SafetyLevel.BLOCK_PATH_INVALID)

    # 权限矩阵取删线两格(普通 / 递归), 五档归属统一出口
    action = permission_of(scope, LINE_DELETE_RECURSIVE if recursive else LINE_DELETE)

    if action == DENY:
        return SafetyResult(blocked=True, needs_confirm=False,
                            message=f"禁止{'递归' if recursive else ''}删除该路径: {path}\n"
                                    f"拦截原因: {SCOPE_TEXT[scope]}",
                            safety_level=SafetyLevel.PATH_FORBIDDEN)

    if action == PASS:
        # 放行: 无确认无拦截, 无"分类"可言, 故不带 safety_level
        return SafetyResult(blocked=False, needs_confirm=False, message="")

    # 需确认: auth_path 必须一并给出 —— safety_gate 确认后凭 auth_path 调 grant_temp_auth
    #   落地临时授权, 缺它则本分支是死路(弹窗承诺授权, 实际无授权落地, 操作照样失败)。
    return SafetyResult(needs_confirm=True, blocked=False, auth_path=path,
                        message=f"待执行操作: {'递归删除目录(含目录内全部子项)' if recursive else '删除文件或目录'}\n"
                                f"目标路径: {path}\n"
                                f"拦截原因: {SCOPE_TEXT[scope]}\n"
                                f"授权时效: 仅本次任务有效, 任务结束自动失效",
                        safety_level=SafetyLevel.DELETE_OUTSIDE_WHITELIST)


def guard_forbidden_delete(file_path: str) -> Optional[str]:
    """删工具执行层: 命中即返回原因, 未命中返回 None — 小欧 2026-10-17

    安全线单源判定, 结果不可改判; 与 delete 工具共用(安全线先拦, 即"双保险内再放行", 日志只此一处)。
    2026-10-19 小欧 - 目录名单收口: 四判据直调(判据已删)改查名单, 与门首同一份判定口径;
      格式化走公共口 classify_path(单一真源)。
    """
    try:
        scope, _ = classify_path(file_path)
    except Exception as e:
        # 格式化/判定失败即 fail-closed: 判不出是否禁区 → 不放行
        return f"路径非法: 路径解析失败({e})"
    if scope in (SCOPE_FORBIDDEN_SYSTEM, SCOPE_FORBIDDEN_NON_SYSTEM):
        return f"禁止删除{SCOPE_TEXT[scope]}: {file_path}"
    return None


def delete_permission(path: str, params: Optional[dict] = None) -> SafetyResult:
    """delete 单路径权限口(唯一封装口) — 供 dual_path_check / shell_path_check 复用 — 小欧 2026-10-18

    2026-10-19 小欧 - 目录名单收口: 归属判定收口到 check_delete_risk 一处(它已按矩阵
    定 拒绝/确认/放行 三档, 并自带非法路径 fail-closed)。禁区(系统/非系统)在矩阵里删格即
    DENY, 与 guard_forbidden_delete 同源同结论, 故此处不再重复调它(原两次 classify_path 属冗余)。
    guard_forbidden_delete 仍是删工具执行层的自持底线, 由 delete 工具直接调用。
    消费方: path_tool_safety_checker(删工具) / shell_path_check(删源) / dual_path_check(删除动作)。
    """
    _params = dict(params or {})
    _params.setdefault("path", path)
    return check_delete_risk(_params)


def check_delete_permission(params: Dict[str, Any]) -> SafetyResult:
    """删线工具级权限口 — 供 path_legality_router [5] 直调 — 小欧 2026-10-18

    2026-10-19 小欧 - 删死参 tool_name: 本口只按参数键判路径, 不用工具名。
    单线删工具路径键恒为 path(L2 已归一); 直接走 delete_permission
    (带本次调用 params, 供 recursive 生效)。未传键 → 放行。
    """
    if "path" not in params:
        return SafetyResult.pass_result()
    return delete_permission(params["path"], params)


__all__ = ["check_delete_risk", "guard_forbidden_delete",
           "delete_permission", "check_delete_permission"]
