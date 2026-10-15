# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 路径检查总入口(自 path_safe_check 迁出)。
#   自 path_safe_check.validate_tool_path(:488-570) 逐字搬迁, 逻辑一字不改, 三处结构性修正:
#     ① 删除 mode 参数与 :515-523 的运行时推断 if 链 —— 动作类型改由 tool_registry
#        查 ToolMetadata.action_kind 静态取得(阶段三落地), 本层不再自己推断。
#     ② 校验对象由 validate_path(path, mode=x) 改为按线直调 read/write/delete_path_check.validate(path),
#        返回值由三元组升为四元组 —— failed_path 由本层填真实解析后路径(BUG-D 修复要点)。
#     ③ 复合工具(含 rename/edit)特判从主干移出, 交 multi_path_check 声明式派发。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳、无兼容入口。
"""
path_check_entry — 路径检查总入口

本模块是 SA5 对外的**唯一入口**, 负责把一次工具调用分派到正确的检查:

  通道 C  action_kind == "none"  无 path 参数的工具 → 直接放行, 不进三线
  通道 B  bash / action_kind == "multi"  多动作 → multi_path_check
  通道 A  action_kind == "read"/"write"/"delete"  单一动作 → 对应线

调用链: SA3 tool_safety_checker._check_known_risks
        → 本模块 validate_tool_path
        → 三线 validate → path_check_common + path_guard.classify_forbidden_path
        → 读 SA6 temp_auth.is_temp_authorized

小欧 2026-10-15
"""

from typing import Any, Dict, Optional, Tuple

from app.safety import shell_path_check, multi_path_check
from app.safety import read_path_check, write_path_check, delete_path_check
from app.tools.registry import tool_registry
from app.tools.tool_constants import PATH_PARAM_KEYS
from app.tools.tools_alias_mapper import normalize_tool_name, normalize_params

# 动作档位 → 线模块: 单一真源在 multi_path_check.LINE_BY_ACTION(2026-10-15 小欧 - P2-22 消除双份)
LINE_BY_ACTION = multi_path_check.LINE_BY_ACTION

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
          category ∈ {"system", "non_system", None} — 供 SA3 显式分流
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

        # bash 走命令专用通道(entry 在此特判, 不经 action_kind 分派); 声明 multi 仅为语义准确。
        if normal_name == "bash":
            return shell_path_check.validate_shell(
                normalized_params.get("command") or "", normalized_params.get("cwd"))

        meta = tool_registry.get_tool(normal_name)
        if meta is None:
            return False, f"工具{normal_name}未注册", None, "system"
        kind = meta.action_kind

        # 通道 C: action_kind=="none" —— 工具定义里无任何路径参数, 与路径安全无关, 直接放行。
        if kind == "none":
            return True, None, None, None

        # 通道 B: 复合工具, 源与目标档位在 MULTI_ACTION_PARAMS 显式声明。
        if kind == "multi":
            return multi_path_check.validate_multi_path(normal_name, normalized_params)

        # 通道 A: 单一动作工具, 静态查表选线, 无 if 链。
        # 2026-10-15 小欧 - P1-10: 未知 action_kind 原经 dict.get 静默降级为写线且无痕迹(配置错误会长期潜伏)。
        #   安全档位仍取写线(fail-closed), 只补可观测性。
        line = LINE_BY_ACTION.get(kind)
        if line is None:
            from app.logger import logger
            logger.warning(
                f"[path_check_entry] 工具 {normal_name} 的 action_kind={kind!r} 不在三线中, "
                f"按写线(fail-closed 最严档)处理; 请在 tool_constants.TOOL_ACTION_KINDS 声明")
            line = write_path_check

        # 遍历所有命中路径参数逐一校验, 任一越权即拒绝(漏洞B修复: 原只取第一个命中参数)
        hit_params = [key for key in PATH_PARAM_KEYS if normalized_params.get(key) is not None]
        for key in hit_params:
            real_path = multi_path_check.resolve_path_param(
                normal_name, key, normalized_params[key], normalized_params)
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
