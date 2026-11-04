# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 写线独立文件。自 path_safe_check.validate_path(:287-400) 拆出写线独有策略, 逐字搬迁不改逻辑(特征一 :323-324 命中 system 禁区→硬拦永不授权; 特征二 :325-333 命中 non_system 禁区→查任务级授权, 无授权则拦; 特征三 :392-395 白名单外→查任务级授权, 无授权则拦); 公共步骤交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 WRITE_MODE。原 validate_path 及 mode 参数已删除(禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 小欧 - validate 改名 validate_write: 三线同名, 经模块引用无法辨识线的语义。
# 2026-10-17 小欧 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path
# 2026-10-17 - 小欧 - 基础封装: 新增 check_write_permission(path) 封装口, 三线统一返回 SafetyResult(签名按各线所需: 仅删线需 params.recursive), 供确认段统一消费。
# 2026-10-17 - 小欧 - 死参清理(方案A): 删 check_write_permission 的 params 死参(写线不用 params)。
# 2026-10-17 - 小欧 - 口径对齐: blocked(系统禁区)分支删去 auth_path=path(硬拦结果无可授权语义, auth_path 定义=白名单外临时授权路径); 与 read/router/delete 的 blocked 口径一致。
# 2026-10-18 - 小欧 - 落地(字面9步): 原单路径口 check_write_permission(path) 更名 write_permission(path)(供 dual/shell 复用);
#   新增工具级 check_write_permission(tool_name, params), 遍历参数经 common.check_tool_paths 逐条走 write_permission, 供 router [5] 直调。
# 2026-10-18 - 小欧 - check_tool_paths 已删除: 单线写工具路径键为 path(download/screen_capture 为 dest), 工具级口直接取该键,
#   仅对 str 值走 write_permission; 空值/穿越由 validate_write 自身判。
# 2026-10-19 - 小欧 - 随路径处理收口: 删 resolve_path_param 调用(解析/绝对化在安全入口单点完成), 直取已格式化值。
# 2026-10-18 - 小欧 - 补【路径名契约】注释: 本安全模块只识别 path/dest 两个路径名; 要求 schema 路径参数名只能是
#   path/dest, 其余历史名仅作别名(L2 已归一到二者); 第三路径名 = 破坏契约(静默漏检)。
# 2026-10-18 - 小欧 - 随契约调整同步 + 措辞补齐: 四个结果补 safety_level 问题来源分类(合法/受保护区/白名单外三条授权线归 path_auth、系统禁区归 forbidden_zone), 分类由本线直给而非上层反查文案; 原 severity 四处取值(safe/dangerous/risk/risk)分别与 blocked/needs_confirm 等价、属重复编码, 一并删 requires_confirmation 随字段改名, docstring 分流说明同步 受保护区写入补"临时"二字、白名单外补时效说明 — 临时授权是任务级、任务结束自动失效, 用户须在弹窗里看到才能与会话级"信任此操作"区分。判定分支与放行条件零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): 放行不再带标签(无确认无拦截, 无分类可言);
#   系统禁区硬拦归 PATH_FORBIDDEN; non_system 任务级授权归 WRITE_PROTECTED、白名单外临时授权归 WRITE_OUT_OF_SCOPE
#   —— 上一条标 path_auth 时两条授权线同标签, 前端无法区分。判定分支与放行条件零变更。
# 2026-10-18 - 小欧 - 文案术语对齐(get_default_allowed_paths / classify_forbidden_path 原文): non_system 判据写
#   "代码目录(含其内部子级)+ 允许根集内的根目录自身及其上级", 白名单外判据写"白名单(系统临时目录/项目根/授权目录/会话工作区)"
#   —— 两者差一个"系统临时目录", 不是同一集合, 不可混用"允许根集"。纯文案, 判定零变更。
# 2026-10-18 小欧 - 两条授权文案改分行(做什么/对什么/原因/范围/时效), 原为一句话堆砌, 弹窗难读。判定零变更。
# 2026-10-19 小欧 - 目录名单收口: 白名单判定改查 path_dir_lists 名单(classify_scope + PERMISSION 写格),
#   原 path_check_common.check_whitelist/resolve_allowed_paths 与 classify_forbidden_path 已删;
#   allowed_paths 死参删除(全库无调用方传它); 拦截原因改用 SCOPE_TEXT, 不再二次转述。
# 2026-10-19 小欧 - 修复写线非法输入回归(空路径/`..`穿越降级为"确认"): 非法输入分支返回的归属由旧
#   category 字面量 "system" 改为 SCOPE_FORBIDDEN_SYSTEM, 与 write_permission 的比较口径一致 → 硬拦。
#   旧口径下 "system" != SCOPE_FORBIDDEN_SYSTEM(=forbidden_system), 会落入确认分支(可被临时授权放行)。
# 2026-10-28 小欧 - 解析失败都放行(北京老陈令「解析失败必须放行, 不拦不弹窗」):
#   归属判定异常(classify_path 抛异常)原归类 system 永不授权硬拦, 改放行。
#   判定失败≠确定危险, 不能因解析能力不足错杀; 确定危险(系统区写入/`..`穿越)仍拦。
#   修改点: validate_write 异常分支 → 放行(True, None, None)。
# 2026-10-19 小欧 - 去冗余: check_write_permission 删死参 tool_name(本口只按参数键判路径, 不用工具名);
#   router 调用点同步改单参。
r"""write_path_check — 写操作路径检查(写线)
★r 前缀必需: 下方说明含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

写线判定(2026-10-19 起, 单一真源 = path_dir_lists):
  一次 classify_scope 取五档归属, 再查 path_dir_lists.PERMISSION 的写格 —— 本线**全库唯一**查白名单的线。

| 归属                | 写 |
|---------------------|-----|
| 禁区·系统           | 拒绝(永不授权) |
| 禁区·非系统         | 确认(任务级授权) |
| 白名单·自身         | 放行 |
| 白名单·下级         | 放行 |
| 白名单外            | 确认(任务级授权) |

  · 非法输入(空路径 / `..` 穿越 / 格式化失败) → 拒绝(BLOCK_PATH_INVALID)。
  · 异常路径归 SCOPE_FORBIDDEN_SYSTEM, 与读/删线口径一致(判不出是否禁区 → 不放行)。
  · 禁区·系统是**唯一永不授权**的一档: 写进去改不回来, 连确认都不给。
  · 确认档可被任务级临时授权放行(is_temp_authorized), 授权落地由调用方(safety_gate)完成。

本线与读/删线的差异: 写产生持久副作用, 故禁区·非系统也走"确认+授权"而非直接拒绝(删线不可逆, 一律硬拒)。
  契约表(读/写/删/递归删 × 五档)见 path_dir_lists.PERMISSION —— 单一真源, 本模块不重复维护。

小欧 2026-10-15 建 / 2026-10-19 小欧 重写
"""

from typing import Any, Dict, Optional, Tuple

import logging                            # 2026-10-20 小欧 - 需授权明细日志引入
logger = logging.getLogger(__name__)

from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17 小欧: 公共步骤从 path_check_common 迁 path_utils
from app.safety.path_dir_lists import (  # 2026-10-19 小欧 - 目录名单收口: 写线判定改走名单+权限矩阵
    classify_path,
    permission_of,
    SCOPE_TEXT,
    SCOPE_FORBIDDEN_SYSTEM,
    SCOPE_FORBIDDEN_NON_SYSTEM,
    LINE_WRITE,
    PASS,
    DENY,
)
from app.safety.temp_auth import is_temp_authorized
from app.safety.safety_result import SafetyLevel, SafetyResult   # 契约: 安全层单源

WRITE_MODE = "write"


def validate_write(file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """原validate_write — 小欧 2026-10-19 目录名单收口: 删 allowed_paths 形参
    (path_check_common 已删, 该形参不再有取值来源; 全库无调用方传它)

    Returns:
        (is_valid, error_message, scope); scope = 五档归属之一(SCOPE_*),
        非法路径时原样带回, 合法路径为 None
    """
    try:
        _reason = reject_reason_empty_path(file_path) or check_preconditions(file_path)  # 空值真源在原子
        if _reason:
            # 非法输入(空路径 / `..` 穿越 / 预条件不满足)一律归系统禁区: 判不出是否禁区 → 不放行、永不授权
            return False, _reason, SCOPE_FORBIDDEN_SYSTEM

        # 2026-10-19 小欧 - 目录名单收口: 一次 classify_scope 取五档归属, 写线动作一律
        #   查 PERMISSION 矩阵(禁区的 system/non_system 二分不再单独表达)
        scope, _rule = classify_path(file_path)
        action = permission_of(scope, LINE_WRITE)
        if action == DENY:
            return False, f"路径位于{SCOPE_TEXT[scope]}, 禁止操作: {file_path}", scope
        if action == PASS:
            return True, None, None
        # 写线特有: 确认档可被任务级临时授权放行(禁区·系统已在上一行硬拦, 永不授权)
        if is_temp_authorized(file_path):
            return True, None, scope
        return False, f"路径位于{SCOPE_TEXT[scope]}: {file_path}", scope
    except Exception as e:
        # 2026-10-28 小欧 - 北京老陈令「解析失败都放行」: 归属判定异常(名单/格式化失败)属解析失败,
        #   改放行(原归类 system 永不授权硬拦)。理由: 判定失败≠确定危险, 不能因解析能力不足错杀。
        logger.warning(f"[write_path_check] 写线判定异常(放行): {file_path!r} ({e})")
        return True, None, None


def write_permission(path: str) -> SafetyResult:
    """写线单路径权限口 — 供 dual_path_check / shell_path_check 复用 — 小欧 2026-10-18
    2026-10-19 小欧 - 目录名单收口: 非法路径按 scope 分流(不再按 system/non_system 二分)
    2026-10-20 小欧 - 需授权分支补明细日志(path+scope+命中规则): 现役需要授权结果只带文案
      档名, 服务端名单现场无快照落库(总闸作用域无 task_id), 事后无法回溯判档依据;
      此日志把"判到哪档/命中哪条规则"当场写死, 复现即自交代。
    """
    _ok, _msg, _scope = validate_write(path)
    if _ok:
        # 放行: 无确认无拦截, 无"分类"可言, 故不带 safety_level
        return SafetyResult(blocked=False, needs_confirm=False, message="")
    if _scope == SCOPE_FORBIDDEN_SYSTEM:
        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
                            safety_level=SafetyLevel.PATH_FORBIDDEN)
    _cls_rule = None
    try:
        from app.safety.path_dir_lists import classify_path as _cp
        _cls_rule = _cp(path)
    except Exception:
        pass
    logger.warning(f"[write_path_check] 写线需授权: path={path}, scope={_scope}, "
                   f"命中规则={_cls_rule}")
    # 拦截原因直接用名单自带的标签文案(SCOPE_TEXT), 与判定同源, 不再二次转述
    return SafetyResult(needs_confirm=True, blocked=False, auth_path=path,
                        message=f"待执行操作: 写入文件\n"
                                f"目标路径: {path}\n"
                                f"拦截原因: {SCOPE_TEXT.get(_scope, '该路径不在允许写入范围内')}\n"
                                f"授权时效: 仅本次任务有效, 任务结束自动失效",
                        safety_level=SafetyLevel.WRITE_FORBIDDEN if _scope == SCOPE_FORBIDDEN_NON_SYSTEM
                                     else SafetyLevel.WRITE_OUTSIDE_WHITELIST)


def check_write_permission(params: Dict[str, Any]) -> SafetyResult:
    """写线工具级权限口 — 供 path_legality_router [4] 直调 — 小欧 2026-10-18

    2026-10-19 小欧 - 删死参 tool_name: 本口只按参数键判路径, 不用工具名。
    单线写工具路径键为 path, download/screen_capture 为 dest; 直接取该键走 write_permission。
    未传键 → 放行; 空值/穿越由 validate_write 自身拦截。

    【路径名契约 ★】本安全模块只识别两个路径参数名: path 与 dest。
    要求各工具 schema 的路径参数名只能是 path 或 dest(download/screen_capture 用 dest);
    其余历史名(source_path/directory/file_name/output_path/destination_path 等)仅作 LLM 别名,
    已由 L2 解析段(action_input_parser._claim 的 normalize_params)归一到 path/dest, 到此已是规范名。
    故此处只做 path/dest 二选一; schema 若出现第三种路径名 = 破坏契约(会静默漏检)。
    """
    key = "path" if "path" in params else "dest"
    if key not in params:
        return SafetyResult.pass_result()
    value = params[key]
    return write_permission(value)


__all__ = ["validate_write", "write_permission", "check_write_permission"]
