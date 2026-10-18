# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 路径检查总入口(自 path_safe_check 迁出)。自 validate_tool_path(:488-570) 逐字搬迁, 三处结构性修正: ①删 mode 参数与 :515-523 运行时推断 if 链, 动作类型改由 tool_registry 查 ToolMetadata.action_kind 静态取得 ②校验对象改按线直调 read/write/delete_path_check.validate, 返回值三元组升四元组(failed_path 由本层填真实解析后路径) ③复合工具(含 rename/edit)特判移出交 dual_path_check。原 validate_path 及 mode 参数已删除(禁止 backward), 无转发壳、无兼容入口。
# 2026-10-15 - 北京老陈裁定: 删"none"通道(通道 A 零路径命中即放行已等价覆盖) + registry_* 豁免(entry 与 bash 特判并列, 注册表键非文件路径)。
# 2026-10-15 - 小欧 - 三堂会审: registry_* 豁免须已注册才生效(防伪造前缀绕过), 移至 get_tool 之后。
# 2026-10-15 - 小欧 - 门前初查: 新增 precheck_path_legality(进门即拦, 失败交调用方 denied 处理) + _EXISTENCE_PARAMS 单源声明。(2026-10-17 已拆出至 path_precheck.py, 本条留档)
# 2026-10-16 - 小欧 - tool去检查化: 合法性规则段(OpCategory/_OP_RULES/check_path_syntax_and_exists)自 file_path_checker 逐字迁入本文件底部(单源单文件合 YAGNI); 纯拼写原子改调 app.utils.path_utils(tools→utils/safety→utils 方向合法)。
# 2026-10-17 北京老陈裁定 - OpCategory 与 check_path_syntax_and_exists 迁往 app.utils.path_utils; 门前初查三处调用点改为三态区分并先过空值原子, 修显式传 None 崩栈。
# 2026-10-17 - 小欧 - 拆分(更名 path_1st_legality_check → path_legality_router, 路径层): 同文件拆出门前初查至 path_precheck.py, 本文件只留 validate_tool_path(读/写/删/dual 分派, 产出 category); 名称正名(原名易被读作合法性入口); _CONTENT_PARAM_KEYS 上移 tool_constants(两文件共用单源)。
# 2026-10-17 - 小欧 - 删 meta None(原 tool_unavailable) 与 startswith("registry_"), 改 PATH_TOOLS 白名单门。
# 2026-10-17 - 小欧 - 返回契约归一: validate_tool_path → check_tool_path_permission, 四元组归一为 SafetyResult; LINE_VALIDATE(旧名函数表) → CHECK_BY_LINE(封装口表); 删线单点传 params(方案A), read/write 无 params; 放行统一 SafetyResult.pass_result()。
# 2026-10-17 - 小欧 - 判定顺序重排(北京老陈裁定): 严格固定为 [1]名归一 → [2]范围门 → [3]参数归一 → [4]read表 → [5]write表 → [6]delete表 → [7]dual表 → [8]bash → [9]返回, 一步不许变; 分派改按四表成员判定(与 registry._resolve_action_kind 同序, 等值), 直调各线封装口; 删 tool_registry/LINE_BY_ACTION/CHECK_BY_LINE 消费(动作类型不再经 action_kind 中转)。
# 2026-10-18 - 小欧 - [38]§12.8 落地(字面9步): 函数体严格 9 步, 每步直调各线工具级封装口; 删逐路径循环(下沉 path_check_common.check_tool_paths)、
#   删"理论不可达"else 兜底分支、删顶层 try/except(fail-closed 兜底随循环下沉)、删死 _WRITE_TARGET_KEYS 与随之无用的 import(PATH_PARAM_KEYS/CONTENT_PARAM_KEYS/reject_reason_empty_path)。
# 2026-10-18 - 小欧 - 参数归一前置(L2 职责): 删 [3] normalize_params(参数名已在 action_input_parser._claim 归一); 步骤 9→8;
#   check_tool_paths 已整体删除, 其 fail-closed 兜底上移到本函数分派段 try/except(单点, 非共享函数); 分派改传原始 params。
# 2026-10-18 - 小欧 - 名归一亦前置: 删 [1] normalize_tool_name(两入口 safety_gate=_normal_name / tool_facade=resolve_registered_tool
#   均已归一到规范名, 本层属第三次冗余); 步骤 8→7, 分派直接用 tool_name; 删随之无用的 import normalize_tool_name。
# 2026-10-18 - 小欧 - 补【路径名契约 ★】注释: 本安全模式只识别 path/dest 两个路径名; 要求 schema 路径参数名只能是
#   path/dest, 其余历史名仅作别名(L2 已归一到二者); 第三路径名 = 破坏契约(静默漏检)。
# 2026-10-18 - 小欧 - 随契约调整同步: 分派段 fail-closed 兜底结果补 safety_level="command_block"(检查过程异常归阻断, 与具体路径禁区区分), 分类由判定点直给; 原 severity="dangerous" 与 blocked=True 等价、属重复编码, 一并删; 返回契约 docstring 随字段改名同步。七步路由顺序与各线直调关系零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): 分派段 fail-closed 兜底由 "command_block" 改 SafetyLevel.BLOCK_COMMAND,
#   同一语义入枚举(检查过程异常属命令层硬拦, 与具体路径禁区区分)。七步路由顺序与各线直调关系零变更。
"""
path_legality_router — [4-2] 路径层(读/写/删/dual 分派, 产出 SafetyResult)

本模块是路径层对外的**唯一入口**, 负责把一次工具调用分派到正确的检查。
参数名归一属前置环节(L2 解析段), 本层不做。

判定顺序(北京老陈裁定, 严格固定, 一步不许变):
  [1] 范围门          非 PATH_TOOLS → 放行
  [2] 在 单read 表?   → read_path_check.check_read_permission
  [3] 在 单write 表?  → write_path_check.check_write_permission
  [4] 在 单delete 表? → delete_path_check.check_delete_permission
  [5] 在 单dual 表?   → dual_path_check.check_dual_permission
  [6] 是 bash?        → shell_path_check.check_shell_permission
  [7] 返回

工具名归一属前置环节(safety_gate 用 _normal_name / tool_facade 用 resolve_registered_tool),
本层不做(避免第三次冗余归一)。

四张表(READ/WRITE/DELETE/DUAL_PATH_TOOLS)由 tool_constants 单源提供, 与
registry._resolve_action_kind 同序查表 → 本模块的"按表分派"与该字段等值。

★[3] 合法性初查(precheck_path_legality)已拆出至同包 path_precheck.py —— 本模块只做 [4-2] 路径路由。

小欧 2026-10-15 建 / 2026-10-17 更名自 path_1st_legality_check / 2026-10-17 判定顺序重排
"""

import logging
from typing import Any, Dict

from app.safety import shell_path_check, dual_path_check
from app.safety import read_path_check, write_path_check, delete_path_check
from app.tools.tool_constants import (
    PATH_TOOLS,
    READ_PATH_TOOLS,
    WRITE_PATH_TOOLS,
    DELETE_PATH_TOOLS,
    DUAL_PATH_TOOLS,
)
from app.safety.safety_result import SafetyLevel, SafetyResult  # 契约: 安全层单源

logger = logging.getLogger(__name__)


def check_tool_path_permission(tool_name: str, params: Dict[str, Any]) -> SafetyResult:
    """工具路径检查总入口 — 小欧 2026-10-15 / 2026-10-17 返回 SafetyResult

    判定顺序(北京老陈裁定, 严格固定, 一步不许变):
      [1] 范围门(非 PATH_TOOLS 放行)
      [2] 单 read 表  → check_read_permission
      [3] 单 write 表 → check_write_permission
      [4] 单 delete 表→ check_delete_permission
      [5] 单 dual 表  → check_dual_permission
      [6] bash        → check_shell_permission
      [7] 返回

    【路径名契约 ★】本安全模式只识别两个路径参数名: path 与 dest。
    要求各工具 schema 的路径参数名只能是 path 或 dest(download/screen_capture 用 dest);
    其余历史名(source_path/directory/file_name/output_path/destination_path 等)仅作 LLM 别名,
    已由 L2 解析段(action_input_parser._claim 的 normalize_params)归一到 path/dest。
    schema 若出现第三种路径名 = 破坏契约(安全层会静默漏检), 守护见 test_p1_layer_ownership.py
    ::test_single_line_tool_path_keys_converge_to_path_or_dest。

    Args:
        tool_name: 工具名(调用方已归一到规范名: safety_gate 用 _normal_name / tool_facade 用 resolve_registered_tool)
        params: 工具参数(解析层 L2 已按 schema 归一, 本层不再归一)

    Returns:
    SafetyResult: 放行(blocked=False, needs_confirm=False) / 拒绝(blocked=True) /
    待确认(needs_confirm=True, auth_path=越权真实路径)。
    """
    # [1] 范围门: 非路径工具直接放行(工具名已前置归一到规范名)
    if tool_name not in PATH_TOOLS:
        return SafetyResult.pass_result()

    try:
        # [2] 单 read 表 → 读线
        if tool_name in READ_PATH_TOOLS:
            return read_path_check.check_read_permission(tool_name, params)

        # [3] 单 write 表 → 写线
        if tool_name in WRITE_PATH_TOOLS:
            return write_path_check.check_write_permission(tool_name, params)

        # [4] 单 delete 表 → 删线
        if tool_name in DELETE_PATH_TOOLS:
            return delete_path_check.check_delete_permission(tool_name, params)

        # [5] 单 dual 表 → dual 线(一调用含多动作, 按参数分别归线)
        if tool_name in DUAL_PATH_TOOLS:
            return dual_path_check.check_dual_permission(tool_name, params)

        # [6] bash → 命令通道(命令串解析出路径后, 内部再分删源/写目标等子类)
        if tool_name == "bash":
            return shell_path_check.check_shell_permission(tool_name, params)
    except Exception as e:
        # fail-closed 单点兜底(接替已删除的 check_tool_paths 内 try/except): 异常归 blocked 永不授权
        return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND, message=f"路径安全检查异常: {e}")

    # [7] 返回
    return SafetyResult.pass_result()


__all__ = ["check_tool_path_permission"]
