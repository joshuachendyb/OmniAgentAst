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
#   _EXISTENCE_PARAMS 单源声明。动因三处:
#   ① 【DRY 下沉】初查原先落在 safety_gate 编排层, op 映射/action→op/PATH_PARAM_KEYS 遍历/
#      DUAL_ACTION_PARAMS 遍历与本文件三份重复, 改表忘同步即分叉; 现收归本模块(路径总入口本就持有
#      "哪个参数该用什么 op"的知识), 编排层只调一行。
#   ② 【BUG 修复·存在性零覆盖】rename 的 path(源)/edit 的 path(被改文件)是 write 档, 按 WRITE 判会跳过
#      存在检查, 实测二者源不存在照样走全套安检+弹窗 —— "前移省弹窗"完全失效。_EXISTENCE_PARAMS 单源声明
#      这两个"write 档但源必须存在"的参数, 命中即按 EXISTS 查。改此表 = 改前移范围。
#   ③ 【BUG 修复·取错源】force 原取原始 params(漏归一化后的别名), 现先取 normalized_params 再回落原值。
#   另: params 入口 `or {}` 归一(None 时原先 params.get 抛异常被 except 吞成静默 fail-open)。
# 2026-10-16 - 小欧 - tool去检查化: 合法性规则段(OpCategory/_OP_RULES/validate_path_layers12)
#   自 file_path_checker 逐字迁入本文件底部(迁移后唯一调用方即本文件 precheck, 单源单文件合 YAGNI);
#   纯拼写原子(保留字符/保留名/多余盘符)改调 app.utils.path_utils(tools→utils/safety→utils 方向合法)。
#   附带: precheck 初查异常补日志(P1, fail-open 必须留痕); UNC 跳过盘符可达性探测(免网络往返);
#   非 str 参数跳过(防 data 内联 dict 被误杀); PATH_PARAM_KEYS 补 search_dir/data(覆盖审计实测原全漏)。
"""
path_1st_legality_check — 路径检查总入口

本模块是 SA5 对外的**唯一入口**, 负责把一次工具调用分派到正确的检查:

   通道 B  bash / registry_* / action_kind == "dual"  → shell_path_check / 豁免 / dual_path_check
   通道 A  action_kind == "read"/"write"/"delete"  单一动作 → 对应线(零路径命中即放行)

调用链: SA3 tool_safety_checker._check_known_risks
        → 本模块 validate_tool_path
        → 三线 validate → path_check_common + path_classify_category.classify_forbidden_path
        → 读 SA6 temp_auth.is_temp_authorized

小欧 2026-10-15
"""

import logging
import os
import string
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.safety import shell_path_check, dual_path_check
from app.safety import read_path_check, write_path_check, delete_path_check
from app.tools.registry import tool_registry
from app.tools.tool_constants import PATH_PARAM_KEYS
from app.tools.tools_alias_mapper import normalize_tool_name, normalize_params
from app.utils.path_utils import (
    path_has_reserved_char,
    path_has_reserved_name,
    path_has_extra_drive,
)

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

# 内容型参数 —— 值可为内联结构(dict/list), 不是路径, 不参与路径判定
_CONTENT_PARAM_KEYS = {"data"}

# 2026-10-15 小欧 - 门前初查单源: 这些参数**虽然工具是 write 档**, 但执行期必须存在。
#   rename 的 path(源)/edit 的 path(被改文件)执行期必须存在, 若按 write 档跳过,
#   "前移省弹窗"对这两个工具即完全失效(实测: 源不存在照样走全套安检+弹窗)。
#   改此表 = 改前移范围。新增"write 档但源必须存在"工具必须登记此表, 否则前移 silently 失效。
#   2026-10-16 小欧 - tool去检查化后 SA1 是唯一合法性检查点, 此表权威性不变。
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
    补"write 档但源必须存在"的两个工具; dual 按 DUAL_ACTION_PARAMS 逐参数分 op。
    读档用 EXISTS 而非 READ_FILE/LIST_DIR: 单动作 read 兼文件与目录, EXISTS 是唯一公分母
    (SA1 是唯一合法性检查点, 宁可口径宽一格由执行期自然失败, 不可误杀合法目录/文件)。

    返回 None = 通过(或不归本层管, 由 validate_tool_path 裁决); 返回 str = 失败原因。
    """
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

        if meta.action_kind == "dual":
            from app.safety.dual_path_check import DUAL_ACTION_PARAMS
            param_map = DUAL_ACTION_PARAMS.get(normal_name)
            if param_map is None:
                return None                                            # 表外交 SA3 fail-closed
            for key, action in param_map.items():
                # 2026-10-17 北京老陈裁定(补到 SA1): 三态区分 —— 没传跳过 / 传了非法值交判 / 合法 str 正常判。
                #   病根: 原 `if value is None: continue` 把"没传"与"显式传 None"混同, 放行到执行期
                #   后 Path(None) 抛 TypeError 崩栈(实测 write(file_path=None))。类型判定不在此重复实现,
                #   直送 validate_path_layers12 第1层(单一真源, 已含 isinstance 检查)。
                if key not in normalized_params:
                    continue                                # 真没传
                value = normalized_params[key]
                if key in _CONTENT_PARAM_KEYS and not isinstance(value, str):
                    continue                            # data 内容型参数: 内联结构非路径
                if isinstance(value, str):
                    value = dual_path_check.resolve_path_param(
                        normal_name, key, value, normalized_params)
                real_path = value
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
            if key not in normalized_params:
                continue                                    # 真没传(不得用 get(key) is None 判, 见 dual 分支裁定)
            value = normalized_params[key]
            if key in _CONTENT_PARAM_KEYS and not isinstance(value, str):
                continue                                # data 内容型参数: 内联结构非路径
            # 2026-10-17 北京老陈裁定(补到 SA1): 显式传入的 None/非 str 一律交 validate_path_layers12
            #   第1层判定(类型/空值单一真源), 不在此重复实现 isinstance 语义。
            if isinstance(value, str):
                value = dual_path_check.resolve_path_param(
                    normal_name, key, value, normalized_params)
            this_op = OpCategory.EXISTS if key in must_exist_keys else op
            ok, err = validate_path_layers12(this_op, value, force=force)
            if not ok:
                return err
        return None
    except Exception as e:
        logger.warning("[SA1] 门前初查自身异常, 已放行交 SA3 兜底: %s", e)
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
                f"[path_1st_legality_check] 工具 {normal_name} 的 action_kind={kind!r} 不在三线中, "
                f"按写线(fail-closed 最严档)处理; 请在 tool_constants 四档声明表之一声明")
            line = write_path_check

        # 遍历所有命中路径参数逐一校验, 任一越权即拒绝(漏洞B修复: 原只取第一个命中参数)
        for key in PATH_PARAM_KEYS:
            if key not in normalized_params:
                continue                                # 真没传(见 precheck 同处裁定)
            value = normalized_params[key]
            if key in _CONTENT_PARAM_KEYS and not isinstance(value, str):
                continue                                # data 内容型参数: 内联结构非路径
            # 2026-10-17 北京老陈裁定(补到 SA1): 显式传入的 None/非 str 交 validate_path_layers12
            #   第1层判定(类型/空值单一真源)。本函数只判权限, 故此处不重复实现类型语义。
            if not isinstance(value, str):
                ok, err = validate_path_layers12(OpCategory.WRITE, value)
                if not ok:
                    return False, err, None, "system"     # fail-closed: 非法类型不可被临时授权放行
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


__all__ = ["validate_tool_path", "precheck_path_legality", "OpCategory", "validate_path_layers12"]


# ══════════════════════════════════════════════════════════════════════
# 下部规则段: 合法性规则(自 file_path_checker 逐字迁入, 2026-10-16 小欧)
# 唯一调用方即本文件 precheck(工具侧 validate_path 已删除), 单源单文件合 YAGNI。
# 纯拼写原子改调 app.utils.path_utils(与 tool 内派生检查同源)。
# ══════════════════════════════════════════════════════════════════════

class OpCategory(Enum):
    WRITE     = "write"
    READ_FILE = "read_file"
    LIST_DIR  = "list_dir"
    EXISTS    = "exists"


_OP_RULES: Dict[OpCategory, Dict[str, Any]] = {
    OpCategory.WRITE:     {"check_exist": False, "must_be": None},
    OpCategory.READ_FILE: {"check_exist": True,  "must_be": "file"},
    OpCategory.LIST_DIR:  {"check_exist": True,  "must_be": "dir"},
    OpCategory.EXISTS:    {"check_exist": True,  "must_be": None},
}


def validate_path_layers12(
    op: OpCategory,
    path: str,
    **options: Any,
) -> Tuple[bool, Optional[str]]:
    """第1层格式 + 第2层存在性/类型 — 小欧 2026-10-15(2026-10-16 迁入本文件, 逻辑零改动, 唯三处收敛)

    收敛: ①保留字符/保留名/多余盘符改调 utils 原子(单源); ②UNC 跳过盘符可达性探测
    (拼写合法即过, 可达性交 p.exists() 一次判定, 免门前网络往返); ③第1层注释同步"零IO"失实口径。
    第1层仍含盘符 exists() 与第2层 exists() 两次 IO —— 门前必要开销, 与执行期不再重复(工具侧已删除)。
    """
    # 第1层
    if not isinstance(path, str) or not path.strip():
        return False, "路径不能为空"
    # 盘符存在性检查（最先做，最外层的快速否决） — 小欧 2026-07-04
    drive = os.path.splitdrive(path)[0]
    if drive and not drive.startswith("\\\\"):
        # 2026-10-16 小欧 - UNC(\\host\\share)跳过可达性探测: 拼写合法即过,
        #   可达性交第2层 p.exists() 一次判定。原先每次 SA1 对 UNC 做网络往返, 不可达主机直接卡门。
        if not os.path.exists(drive + "\\"):
            avail = [f"{l}:" for l in string.ascii_uppercase if os.path.exists(f"{l}:\\")]
            return False, f"驱动器: {drive}不存在。可用驱动器: {', '.join(avail)}"
    if drive:
        extra = path_has_extra_drive(path)   # 纯内存拼写检查, UNC 同样适用
        if extra:
            return False, extra
    # 只检查文件名部分（Path(...).name），排除路径分隔符和盘符:号 — 小欧 2026-07-04
    _fname = Path(path).name
    bad = path_has_reserved_char(_fname)
    if bad:
        return False, f"文件: {_fname}名包含Windows保留字符"
    reserved = path_has_reserved_name(path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名"

    # 第2层
    rule = _OP_RULES[op]
    if rule["check_exist"]:
        p = Path(path)
        if not p.exists():
            # 幂等删除: force=True 时不存在即视为已删除,不报错(delete 专用) — 北京老陈 2026-07-12
            if op == OpCategory.EXISTS and options.get("force"):
                return True, None
            logger.warning("[TOCTOU] path=%s op=%s drive_exists=%s parent_exists=%s parent_dir=%s",
                           path, op.value,
                           os.path.exists(os.path.splitdrive(path)[0] + "\\") if os.path.splitdrive(path)[0] else "N/A",
                           p.parent.exists(), str(p.parent))
            return False, "路径不存在: " + path
        if rule["must_be"] == "file" and not p.is_file():
            return False, path + "不是文件"
        if rule["must_be"] == "dir" and not p.is_dir():
            return False, path + "不是目录"
    return True, None
