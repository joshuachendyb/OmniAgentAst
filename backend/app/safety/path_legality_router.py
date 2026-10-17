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
"""
path_legality_router — [4-2] 路径层(读/写/删/dual 分派, 产出 SafetyResult)

本模块是路径层对外的**唯一入口**, 负责把一次工具调用分派到正确的检查。

判定顺序(北京老陈裁定, 严格固定, 一步不许变):
  [1] 名归一          normalize_tool_name
  [2] 范围门          非 PATH_TOOLS → 放行
  [3] 参数归一        normalize_params
  [4] 在 单read 表?   → read_path_check.check_read_permission
  [5] 在 单write 表?  → write_path_check.check_write_permission
  [6] 在 单delete 表? → delete_path_check.check_delete_permission
  [7] 在 单dual 表?   → dual_path_check.check_dual_permission
  [8] 是 bash?        → shell_path_check.check_shell_permission
  [9] 返回

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
    PATH_PARAM_KEYS,
    CONTENT_PARAM_KEYS,
    PATH_TOOLS,
    READ_PATH_TOOLS,
    WRITE_PATH_TOOLS,
    DELETE_PATH_TOOLS,
    DUAL_PATH_TOOLS,
)
from app.tools.tools_alias_mapper import normalize_tool_name, normalize_params
from app.utils.path_utils import reject_reason_empty_path
from app.tools.tool_types import SafetyResult  # 2026-10-17 小欧 - 路径层返回 SafetyResult

logger = logging.getLogger(__name__)

# 写入类路径参数 —— 一律指向"数据落到哪里", 恒按写线判。2026-10-15 小欧 - P1-11
_WRITE_TARGET_KEYS = {"dest", "target_path", "output_path", "destination_path"}


def check_tool_path_permission(tool_name: str, params: Dict[str, Any]) -> SafetyResult:
    """工具路径检查总入口 — 小欧 2026-10-15 / 2026-10-17 返回 SafetyResult

    判定顺序(北京老陈裁定, 严格固定, 一步不许变):
      [1] 名归一 → [2] 范围门(非 PATH_TOOLS 放行) → [3] 参数归一
      [4] 单 read 表  → check_read_permission
      [5] 单 write 表 → check_write_permission
      [6] 单 delete 表→ check_delete_permission
      [7] 单 dual 表  → check_dual_permission
      [8] bash        → check_shell_permission
      [9] 返回

    Args:
        tool_name: 工具名(LLM 传入的原始名)
        params: 工具参数

    Returns:
        SafetyResult: 放行(blocked=False, requires_confirmation=False) / 拒绝(blocked=True) /
          待确认(requires_confirmation=True, auth_path=越权真实路径)。
    """
    try:
        # [1] 名归一(防别名漏判)
        normal_name = normalize_tool_name(tool_name)

        # [2] 范围门: 非路径工具直接放行
        if normal_name not in PATH_TOOLS:
            return SafetyResult.pass_result()

        # [3] 参数归一: 别名 → 规范名(LLM 常传 PARAM_ALIASES 里的别名, 归一后取路径参数才不漏检)
        normalized_params, _ = normalize_params(normal_name, params)

        # [4] 单 read 表 → 读线
        if normal_name in READ_PATH_TOOLS:
            line = read_path_check
        # [5] 单 write 表 → 写线
        elif normal_name in WRITE_PATH_TOOLS:
            line = write_path_check
        # [6] 单 delete 表 → 删线
        elif normal_name in DELETE_PATH_TOOLS:
            line = delete_path_check
        # [7] 单 dual 表 → dual 线(一调用含多动作, 按参数分别归线)
        elif normal_name in DUAL_PATH_TOOLS:
            return dual_path_check.check_dual_permission(normal_name, normalized_params)
        # [8] bash → 命令通道(命令串解析出路径后，内部再分删源/写目标等子类)
        elif normal_name == "bash":
            return shell_path_check.check_shell_permission(
                normalized_params.get("command") or "", normalized_params.get("cwd"))
        # 理论不可达(能过 [2] 门者必属上述五类) → fail-closed 按写线
        else:
            logger.warning(
                f"[path_legality_router] 工具 {normal_name} 不在任何路径档表, 按写线(fail-closed 最严档)处理")
            line = write_path_check

        # 逐路径参数判定(单动作三线共用): 遍历所有命中路径参数, 任一越权即返回
        for key in PATH_PARAM_KEYS:
            if key not in normalized_params:
                continue                                # 真没传(见 precheck 同处裁定)
            value = normalized_params[key]
            if key in CONTENT_PARAM_KEYS and not isinstance(value, str):
                continue                                # data 内容型参数: 内联结构非路径
            # 空值交底层原子(唯一真源)
            _empty = reject_reason_empty_path(value)
            if _empty:
                return SafetyResult(blocked=True, severity="dangerous", message=_empty)
            if not isinstance(value, str):
                continue
            real_path = dual_path_check.resolve_path_param(
                normal_name, key, value, normalized_params)
            # 2026-10-15 小欧 - P1-11: dest/target_path 等是写入目标, 与工具动作无关, 恒走写线。
            param_line = write_path_check if key in _WRITE_TARGET_KEYS else line
            # 方案A: 仅删线需 params(recursive); read/write 线无 params 死参
            if param_line is delete_path_check:
                result = delete_path_check.check_delete_permission(real_path, normalized_params)
            elif param_line is write_path_check:
                result = write_path_check.check_write_permission(real_path)
            else:
                result = read_path_check.check_read_permission(real_path)
            if result.blocked or result.requires_confirmation:
                return result

        # [9] 返回
        return SafetyResult.pass_result()
    except Exception as e:
        # 2026-08-11 小欧 fix D1残留: 兜底异常归 blocked(永不授权硬拦) —
        #   与三线各 except 分支"blocked"口径全链一致(T2 硬拦永不授权)
        return SafetyResult(blocked=True, severity="dangerous", message=f"路径安全检查异常: {e}")


__all__ = ["check_tool_path_permission"]
