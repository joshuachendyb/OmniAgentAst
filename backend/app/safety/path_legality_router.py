# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 路径检查总入口(自 path_safe_check 迁出)。
#   自 path_safe_check.validate_tool_path(:488-570) 逐字搬迁, 逻辑一字不改, 三处结构性修正:
#     ① 删除 mode 参数与 :515-523 的运行时推断 if 链 —— 动作类型改由 tool_registry
#        查 ToolMetadata.action_kind 静态取得(阶段三落地), 本层不再自己推断。
#     ② 校验对象由 validate_path(path, mode=x) 改为按线直调 read/write/delete_path_check.validate(path),
#        返回值由三元组升为四元组 —— failed_path 由本层填真实解析后路径(BUG-D 修复要点)。
#     ③ 复合工具(含 rename/edit)特判从主干移出, 交 dual_path_check 声明式派发。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳、无兼容入口。
# 2026-10-15 - 北京老陈裁定: 删"none"通道(通道 A 零路径命中即放行已等价覆盖) + registry_* 豁免(entry 与 bash 特判并列, 注册表键非文件路径)。
# 2026-10-15 - 小欧 - 三堂会审: registry_* 豁免须已注册才生效(防伪造前缀绕过), 移至 get_tool 之后。
# 2026-10-15 - 小欧 - 门前初查: 新增 precheck_path_legality(SA1 进门即拦, 失败交调用方 denied 处理) +
#   _EXISTENCE_PARAMS 单源声明。(2026-10-17 已拆出至 path_precheck.py, 本条留档)
# 2026-10-16 - 小欧 - tool去检查化: 合法性规则段(OpCategory/_OP_RULES/check_path_syntax_and_exists)
#   自 file_path_checker 逐字迁入本文件底部(迁移后唯一调用方即本文件 precheck, 单源单文件合 YAGNI);
#   纯拼写原子(保留字符/保留名/多余盘符)改调 app.utils.path_utils(tools→utils/safety→utils 方向合法)。
# 2026-10-17 北京老陈裁定 - OpCategory 与 check_path_syntax_and_exists 迁往 app.utils.path_utils; SA1 三处调用点改为三态区分并先过空值原子, 修显式传 None 崩栈。
# 2026-10-17 - 小欧 - 文档[37] 拆分(更名 path_1st_legality_check → path_legality_router, SA5 路径层):
#   同文件拆出 SA1 门前初查(precheck_path_legality + _EXISTENCE_PARAMS)至 path_precheck.py;
#   本文件只留 SA5 validate_tool_path(读/写/删/dual 分派, 产出 category)。
#   名称正名: 原名易被读作 SA1 入口, 实为 SA5 路径路由。_CONTENT_PARAM_KEYS 上移 tool_constants.CONTENT_PARAM_KEYS(两文件共用单源)。
"""
path_legality_router — SA5 路径层(读/写/删/dual 分派, 产出 category)

本模块是 SA5 对外的**唯一入口**, 负责把一次工具调用分派到正确的检查:

    通道 B  bash / registry_* / action_kind == "dual"  → shell_path_check / 豁免 / dual_path_check
    通道 A  action_kind == "read"/"write"/"delete"  单一动作 → 对应线(零路径命中即放行)

调用链: SA3 tool_safety_checker._check_known_risks
        → 本模块 validate_tool_path
        → 三线 validate → path_check_common + path_classify_category.classify_forbidden_path
        → 读 SA6 temp_auth.is_temp_authorized

★SA1 门前初查(precheck_path_legality)已拆出至同包 path_precheck.py —— 本模块只做 SA5 路径路由。

小欧 2026-10-15 建 / 2026-10-17 更名自 path_1st_legality_check
"""

import logging
from typing import Any, Dict, Optional, Tuple

from app.safety import shell_path_check, dual_path_check
from app.safety import read_path_check, write_path_check, delete_path_check
from app.tools.registry import tool_registry
from app.tools.tool_constants import PATH_PARAM_KEYS, CONTENT_PARAM_KEYS
from app.tools.tools_alias_mapper import normalize_tool_name, normalize_params
from app.utils.path_utils import reject_reason_empty_path

logger = logging.getLogger(__name__)

# 动作档位 → 线模块: 单一真源在 dual_path_check.LINE_BY_ACTION(2026-10-15 小欧 - P2-22 消除双份)
LINE_BY_ACTION = dual_path_check.LINE_BY_ACTION

# 2026-10-15 北京老陈裁定 - 三线 validate 改 validate_read/write/delete 后, 此表给出
#   「线模块 -> 本线校验函数」, 调用点一次查表即知走哪条线(同名 validate 无法辨识)。
LINE_VALIDATE = {
    read_path_check: read_path_check.validate_read,
    write_path_check: write_path_check.validate_write,
    delete_path_check: delete_path_check.validate_delete,
}

# 写入类路径参数 —— 一律指向"数据落到哪里", 恒按写线判。2026-10-15 小欧 - P1-11
_WRITE_TARGET_KEYS = {"dest", "target_path", "output_path", "destination_path"}


def validate_tool_path(tool_name: str, params: Dict[str, Any]
                       ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """工具路径检查总入口 — 小欧 2026-10-15

    自 path_safe_check.validate_tool_path(:488-570) 迁出。

    Args:
        tool_name: 工具名(LLM 传入的原始名)
        params: 工具参数

    Returns:
        (is_valid, error_message, failed_path, category)
          failed_path = 首个校验失败的真实路径(临时授权 auth_path 用, 成功时为 None)
          category ∈ {"system", "non_system", "tool_unavailable", None} — 供 SA3 显式分流
          ★2026-10-16 补: 原 docstring 只写三项, 漏 "tool_unavailable"(未注册工具硬拦)。
            本函数是 category 的唯一产出者, **新增取值必须同步 SA3 的分流分支**, 否则漏判。
    """
    # 2026-10-15 小欧 - P1-9: 异常分支原恒返 failed_path=None, 但 real_path 已知(异常多发生在
    #   resolve_path_param / line.validate 中途), 丢失会让 SA3 的 auth_path 定位错位。现带回。
    current_path: Optional[str] = None
    try:
        normal_name = normalize_tool_name(tool_name)  # 防别名漏判

        # 参数别名先归一化再取路径参数 —
        #   LLM 常传 PARAM_ALIASES 里的别名(如 rename.new_name→dest/copy.src→path/dst→dest),
        #   原代码 hit_params 直接查原始 params, 别名参数命中不了 PATH_PARAM_KEYS → 路径越权漏检。
        #   此处用 normalize_params 归一化后找路径参数, 校验对象与工具实际落盘路径一致(增强不退化)。
        normalized_params, _ = normalize_params(normal_name, params)

        # bash 走命令专用通道(entry 在此特判, 不经 action_kind 分派); 声明 dual 仅为语义准确。
        if normal_name == "bash":
            return shell_path_check.validate_shell(
                normalized_params.get("command") or "", normalized_params.get("cwd"))

        meta = tool_registry.get_tool(normal_name)
        if meta is None:
            # 2026-10-16 - 小欧 - 未注册工具单列 tool_unavailable: 原报成"系统禁区路径越权",
            #   误导 LLM/用户去改路径。仍 fail-closed(未注册工具本就无法执行)。
            return False, f"工具 {normal_name} 不可用(未注册)", None, "tool_unavailable"

        # registry_* 的 path 是注册表键而非文件路径, 不进文件判定(2026-10-15 北京老陈裁定:
        # 非文件工具不得进四档声明表凑数, 豁免放 entry 与 bash 特判并列)。
        # 2026-10-15 小欧 - 三堂会审: 豁免须已注册才生效, 未注册的 registry_* 仍走上方的
        #   system 硬拦, 防伪造工具名前缀绕过。
        if normal_name.startswith("registry_"):
            return True, None, None, None
        kind = meta.action_kind

        # 通道 B: 复合工具, 源与目标档位在 DUAL_ACTION_PARAMS 显式声明。
        if kind == "dual":
            return dual_path_check.validate_dual_path(normal_name, normalized_params)

        # 通道 A: 单一动作工具, 静态查表选线, 无 if 链。
        # 2026-10-15 小欧 - P1-10: 未知 action_kind 原经 dict.get 静默降级为写线且无痕迹(配置错误会长期潜伏)。
        #   安全档位仍取写线(fail-closed), 只补可观测性。
        line = LINE_BY_ACTION.get(kind)
        if line is None:
            logger.warning(
                f"[path_legality_router] 工具 {normal_name} 的 action_kind={kind!r} 不在三线中, "
                f"按写线(fail-closed 最严档)处理; 请在 tool_constants 四档声明表之一声明")
            line = write_path_check

        # 遍历所有命中路径参数逐一校验, 任一越权即拒绝(漏洞B修复: 原只取第一个命中参数)
        for key in PATH_PARAM_KEYS:
            if key not in normalized_params:
                continue                                # 真没传(见 precheck 同处裁定)
            value = normalized_params[key]
            if key in CONTENT_PARAM_KEYS and not isinstance(value, str):
                continue                                # data 内容型参数: 内联结构非路径
            # 空值交底层原子(唯一真源)
            _empty = reject_reason_empty_path(value)
            if _empty:
                return False, _empty, None, "system"       # fail-closed: 非法类型不可被临时授权放行
            if not isinstance(value, str):
                continue
            real_path = dual_path_check.resolve_path_param(
                normal_name, key, value, normalized_params)
            current_path = real_path
            # 2026-10-15 小欧 - P1-11: dest/target_path 等是写入目标, 与工具动作无关。实测 read 工具携带
            #   dest=C:\Windows\evil.txt 时跟读线判会放行, 故这批参数恒走写线。
            param_line = write_path_check if key in _WRITE_TARGET_KEYS else line
            valid, err, category = LINE_VALIDATE[param_line](real_path)
            if not valid:
                # failed_path 取真正越权参数的真实路径(BUG-D), 不再固定 path-or-dest
                return False, err, real_path, category

        return True, None, None, None
    except Exception as e:
        # 2026-08-11 小欧 fix D1残留: 兜底异常归 category="system"(永不授权硬拦) —
        #   异常/恶意路径理论上仍可被临时授权放行(与D1同源隐患);
        #   与三线各 except 分支"system"口径全链一致(T2 硬拦永不授权)
        return False, f"路径安全检查异常: {e}", current_path, "system"


__all__ = ["validate_tool_path"]
