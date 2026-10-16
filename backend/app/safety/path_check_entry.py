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
# 2026-10-15 - 北京老陈裁定: 删"none"通道(通道 A 零路径命中即放行已等价覆盖) + registry_* 豁免(entry 与 bash 特判并列, 注册表键非文件路径)。
# 2026-10-15 - 小欧 - 三堂会审: registry_* 豁免须已注册才生效(防伪造前缀绕过), 移至 get_tool 之后。
# 2026-10-15 - 小欧 - 门前初查: 新增 precheck_path_legality(SA1 进门即拦, 失败交调用方 denied 处理) +
#   _EXISTENCE_PARAMS 单源声明。动因三处:
#   ① 【DRY 下沉】初查原先落在 safety_gate 编排层, op 映射/action→op/PATH_PARAM_KEYS 遍历/
#      MULTI_ACTION_PARAMS 遍历与本文件三份重复, 改表忘同步即分叉; 现收归本模块(路径总入口本就持有
#      "哪个参数该用什么 op"的知识), 编排层只调一行。
#   ② 【BUG 修复·存在性零覆盖】rename 的 path(源)/edit 的 path(被改文件)是 write 档, 按 WRITE 判会跳过
#      存在检查, 实测二者源不存在照样走全套安检+弹窗 —— "前移省弹窗"完全失效。_EXISTENCE_PARAMS 单源声明
#      这两个"write 档但源必须存在"的参数, 命中即按 EXISTS 查。改此表 = 改前移范围。
#   ③ 【BUG 修复·取错源】force 原取原始 params(漏归一化后的别名), 现先取 normalized_params 再回落原值。
#   另: params 入口 `or {}` 归一(None 时原先 params.get 抛异常被 except 吞成静默 fail-open)。
"""
path_check_entry — 路径检查总入口

本模块是 SA5 对外的**唯一入口**, 负责把一次工具调用分派到正确的检查:

   通道 B  bash / registry_* / action_kind == "multi"  → shell_path_check / 豁免 / multi_path_check
   通道 A  action_kind == "read"/"write"/"delete"  单一动作 → 对应线(零路径命中即放行)

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

# 2026-10-15 小欧 - 门前初查单源: 这些参数**虽然工具是 write 档**, 但执行期必须存在。
#   rename 的 path(源)/edit 的 path(被改文件)由工具内 validate_path(EXISTS/READ_FILE) 查存在,
#   若按 write 档跳过, "前移省弹窗"对这两个工具即完全失效(实测: 源不存在照样走全套安检+弹窗)。
#   改此表 = 改前移范围, 与 entry 的权威同源(op 表不在编排层重写)。
_EXISTENCE_PARAMS: Dict[str, set] = {
    "rename": {"path"},
    "edit": {"path"},
}


def precheck_path_legality(tool_name: str, params: Dict[str, Any]) -> Optional[str]:
    """门前初查: 第1层格式 + 第2层存在性 — 小欧 2026-10-15

    SA1 进门即拦(省信任预查/SA3/HITL三步), 失败原因交调用方按 denied 处理。
    只取"是否存在", 警告层(第3层)完全不跑 —— 门前参数不全(content/recursive/overwrite 等),
    且警告要贴近执行才有意义。执行期工具内 validate_path 原样全跑(第2层复查防 TOCTOU + 第3层警告)。

    op 知识与本文件同源: 单动作读/删 → EXISTS; write → WRITE(跳过存在) + _EXISTENCE_PARAMS
    补"write 档但源必须存在"的两个工具; multi 按 MULTI_ACTION_PARAMS 逐参数分 op。

    返回 None = 通过(或不归本层管, 由 validate_tool_path 裁决); 返回 str = 失败原因。
    """
    from app.tools.validate.file_path_checker import validate_path_layers12, OpCategory
    from app.tools.tools_alias_mapper import normalize_params

    params = params or {}
    try:
        normal_name = normalize_tool_name(tool_name)
        # bash(命令通道)/registry_*(注册表键非文件路径)与未注册工具: 均交 validate_tool_path 裁决
        if normal_name == "bash" or normal_name.startswith("registry_"):
            return None
        meta = tool_registry.get_tool(normal_name)
        if meta is None:
            return None
        normalized_params, _ = normalize_params(normal_name, params)
        must_exist_keys = _EXISTENCE_PARAMS.get(normal_name, set())
        force = bool(normalized_params.get("force", params.get("force", False)))

        if meta.action_kind == "multi":
            from app.safety.multi_path_check import MULTI_ACTION_PARAMS
            param_map = MULTI_ACTION_PARAMS.get(normal_name)
            if param_map is None:
                return None                                            # 表外交 SA3 fail-closed
            for key, action in param_map.items():
                value = normalized_params.get(key)
                if value is None:
                    continue
                real_path = multi_path_check.resolve_path_param(
                    normal_name, key, value, normalized_params)
                if action == "read":
                    op = OpCategory.EXISTS
                elif action == "delete":
                    op = OpCategory.EXISTS
                else:
                    op = OpCategory.WRITE                              # 写目标只查格式
                    if key in must_exist_keys:
                        op = OpCategory.EXISTS
                ok, err = validate_path_layers12(op, real_path, force=force)
                if not ok:
                    return err
            return None

        if meta.action_kind == "read":
            op = OpCategory.EXISTS
        elif meta.action_kind == "delete":
            op = OpCategory.EXISTS
        elif meta.action_kind == "write":
            op = OpCategory.WRITE
        else:
            return None                                                # 未知档位交 SA3 fail-closed
        for key in PATH_PARAM_KEYS:
            value = normalized_params.get(key)
            if value is None:
                continue
            real_path = multi_path_check.resolve_path_param(
                normal_name, key, value, normalized_params)
            this_op = OpCategory.EXISTS if key in must_exist_keys else op
            ok, err = validate_path_layers12(this_op, real_path, force=force)
            if not ok:
                return err
        return None
    except Exception:
        return None                                                    # 初查自身异常不拦路: SA3+执行期两道还在


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
            # 2026-10-16 - 小欧 - 未注册工具单列 tool_unavailable: 原报成"系统禁区路径越权",
            #   误导 LLM/用户去改路径。仍 fail-closed(未注册工具本就无法执行)。
            return False, f"工具 {normal_name} 不可用(未注册)", None, "tool_unavailable"

        # registry_* 的 path 是注册表键而非文件路径, 不进文件判定(2026-10-15 北京老陈裁定:
        # 非文件工具不得进 PATH_ACTION_KINDS 凑数, 豁免放 entry 与 bash 特判并列)。
        # 2026-10-15 小欧 - 三堂会审: 豁免须已注册才生效, 未注册的 registry_* 仍走上方的
        #   system 硬拦, 防伪造工具名前缀绕过。
        if normal_name.startswith("registry_"):
            return True, None, None, None
        kind = meta.action_kind

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
                f"按写线(fail-closed 最严档)处理; 请在 tool_constants.PATH_ACTION_KINDS 声明")
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


__all__ = ["validate_tool_path", "precheck_path_legality"]
