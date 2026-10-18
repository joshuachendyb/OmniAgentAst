# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 多动作通道。承接收"一条调用内混着多个动作"的检查: 6 个复合工具的源与目标分别判定(DUAL_ACTION_PARAMS 声明式派发); 补两处缺口 G1(白名单漏 rename, rename 的 path 源按 write 判→误拦合法读源, 改声明表全列六个不再靠 if 链) G2(参数键只认 src/source_path 不认 path/dest 且 edit 未考虑, copy 的 path 按 write 判, 现声明表直给每参数动作类型); 手法: _validate_shell_write_targets 逐字搬迁只改 import 路径。
# 2026-10-15 - 北京老陈裁定(真分开): 声明表全 write 是摆设, 改为源=读线+系统源外泄拦截、目标=写线、move 源=删线; 单路径 edit 移出本表(改走写线); 并修复 LINE_BY_ACTION[action].validate 旧名残留(三线已改名, 旧调用致 6 工具全瘫)。
# 2026-10-15 - 小欧 - 三堂会审: validate_dual_path 的 param_map is None 原静默放行, 改 fail-closed(命中路径参数逐个走写线, 零命中返 False/system) + warning 留痕。
# 2026-10-17 - 小欧 - 第十章: delete 动作(仅 move 源)改纯调 delete_path_check.check_delete_permission(判定全下沉, 本层不重判); blocked→拒(category=system), requires_confirmation→当通过(本通道无弹窗, 老陈裁定)。读/写线不变。
# 2026-10-17 - 小欧 - 返回契约归一: validate_dual_path → check_dual_permission, 四元组归一为 SafetyResult; 三线改调新封装口(check_read/write_permission), 放行统一 SafetyResult.pass_result()。
# 2026-10-17 - 小欧 - 裁定: move 源=删源→写目标(删源须弹窗), copy 源=读源→写目标(读源放行), 两者逻辑不同; delete 动作补 recursive=os.path.isdir(real_path), 且 requires_confirmation 由"当通过"改为**返回弹窗**(与单 delete 工具对齐); R6(工作区外递归)仍硬拦。copy 读源分支不变。
# 2026-10-17 - 小欧 - DUAL_ACTION_PARAMS 表体上移 tool_constants(与 DUAL_PATH_TOOLS 同层), 本层改 import 消费。
# 2026-10-17 - 小欧 - 删 LINE_BY_ACTION(死表): 唯一消费方 path_legality_router 已改按四表成员分派, 本表零消费, 按 YAGNI 删除。
# 2026-10-18 - 小欧 - [38]§12.6 落地(单路径口正名跟改): 三线单路径封装口更名 read/write/delete_permission, 本模块 4 处调用点同步跟改, 判定逻辑零改动。
# 2026-10-18 - 小欧 - 北京老陈裁定(归类错误修复): generate_chart 移入双路径(data=read/dest=write), 本模块补 CONTENT_PARAM_KEYS 跳过(与 path_precheck:79 同口径), 防 data 内联 dict 被当路径送 read_permission 崩栈误拦。
# 2026-10-18 - 小欧 - 参数归一前置 + 常量清理: 删 CONTENT_PARAM_KEYS 依赖, 内容守卫改类型判断(非 str 非 None 跳过);
#   fail-closed 分支不再扫 PATH_PARAM_KEYS(11 键), 只认 path/dest(dual 工具的两个路径键)。参数名已在 L2 归一。
# 2026-10-18 - 小欧 - 随契约调整同步: 四处三线结果的"是否需确认"判读改 needs_confirm; 两处自建结果补 safety_level —— 未带任何路径参数属调用形状问题、归 tool_delete, 系统源外泄拦截归 forbidden_zone, 分类由本层直给而非上层反查文案。判定逻辑与返回结构零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): 无路径参数的调用形状问题硬拦归 BLOCK_PATH_INVALID(上一条标 tool_delete,
#   把"参数形状不对"说成"删除"); 系统源外泄拦截归 PATH_FORBIDDEN。判定逻辑与返回结构零变更。
# 2026-10-19 - 小欧 - 全参数取最严(修复 under-block, 与 shell_path_check._judge_actions 同款):
#   原循环首个 needs_confirm 即返回, 会挡住其后系统目标写的 blocked(move 源越界 + 目标系统 → 硬拦降级为可授权)。
#   改为 blocked 即返、needs_confirm 暂存(取先到者)判完参数, 无 blocked 时才回 needs_confirm。各线判定逻辑零改动。
r"""dual_path_check — 双路径通道(6 个复合工具: copy/move/compress/extract/rename/generate_chart)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

本模块判定"一次调用里多个路径动作": 源与目标各归其线。
设计要点: 参数动作类型由 DUAL_ACTION_PARAMS 声明式单源给出,
新增复合工具只改这张表, 不改判定代码(OCP)。
原 path_safe_check.py:558-560 的 if 链(白名单四个工具 + 参数键只认 src/source_path)已废弃。

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块把每个参数派给 read/write/delete 三线, 三线各自只返回「放行/拒绝」两态;
  表里的"确认"(弹窗授权)发生在**调用方** path_tool_safety_checker, "确认(根外递归, 来自 R6 层)"来自
  delete_path_check.check_delete_risk 的 R6 工作区边界层。→ "确认"格与本文件代码对不上是**正常的**, 那是上层行为。

| 区域                                       | category   | 读   | 写            | 删           |
|--------------------------------------------|------------|------|---------------|--------------|
| 空路径 / 含 `..` 路径穿越(非法输入)         | —          | 拒绝 | 拒绝          | 拒绝         |
| 磁盘根(任意盘符)                           | system     | 放行 | 拒绝          | 拒绝         |
| 系统敏感文件(config\SAM/SECURITY/SOFTWARE 等)| system    | 放行 | 拒绝          | 拒绝         |
| 系统目录(Windows/ProgramFiles/ProgramData/Boot/WinSxS) | system | 放行 | 拒绝 | 拒绝         |
| 代码目录 —— 自身及内部所有子级             | non_system | 放行 | 确认(任务级)  | 拒绝         |
| 授权目录 —— 自身及其上级祖先               | non_system | 放行 | 确认(任务级)  | 拒绝         |
| 白名单内(path_env.get_default_allowed_paths 动态取值) | None | 放行 | 放行 | 确认(根外递归, 来自 R6 层) |
| 白名单外普通路径                           | None       | 放行 | 确认(临时授权)| 确认         |
| 异常/恶意路径                              | system     | 拒绝 | 拒绝          | 拒绝         |

两个 non_system 类别的正式定义(勿凭字面猜):
  · 代码目录 = get_code_root()       判**自身 + 内部所有子级**; **父级不拦**
  · 授权目录 = get_allowed_roots()   判**自身 + 上级祖先**; **内部不拦**
               = 用户项目根 + **授权目录** + 会话工作区(session_workspace_paths) 三个来源

★本通道按 DUAL_ACTION_PARAMS 把每个参数派到 read/write/delete 三线, 故三列都可能命中。
★删线对两个 non_system 类一律硬拦(抹除不可逆), 故 copy/move 的**源**若落在代码目录内直接拒。
★本表是禁区分类的结果说明, 规则改动须同步本表, 勿只改表。

小欧 2026-10-15 建 / 2026-10-16 老陈裁定补权限总表
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from app.safety import read_path_check, write_path_check, delete_path_check
from app.safety.path_classify_category import classify_forbidden_path  # 2026-10-15 系统源外泄拦截用
from app.safety.safety_result import SafetyLevel, SafetyResult  # 契约: 安全层单源
from app.tools.tool_constants import DUAL_ACTION_PARAMS  # 2026-10-17 小欧 - 表体上移工具层(与 DUAL_PATH_TOOLS 同层); 2026-10-18 删 CONTENT_PARAM_KEYS(改类型判断)


# ── 复合工具参数动作声明(表体在 tool_constants.DUAL_ACTION_PARAMS, 与 DUAL_PATH_TOOLS 同层) ──
# 2026-10-15 小欧 - 阶段三定稿 / 2026-10-15 北京老陈裁定(真分开):
#   源与目标各归其线, 不得全按 write 糊弄。
#     copy/compress/extract: 源只读 → 读线; 但读线放行系统目录, 故须另加「系统源外泄拦截」
#       (否则可把 C:\Windows 数据搬运出去, 实测 validate_read(C:\Windows\a.txt)=True)
#     move: 源搬走=删 → 删线; 目标落地 → 写线
#     rename: 同一对象改名改写 → 写线(与之前一致, 零退化)
#   表体已于 2026-10-17 上移 tool_constants(与"哪些工具是 dual"的 DUAL_PATH_TOOLS 同层), 本层仅消费。

def resolve_path_param(tool_name: str, key: str, value: str, params: Dict[str, Any]) -> str:
    """工具逻辑路径参数→真实文件系统路径 — 小欧 2026-10-15

    自 path_safe_check._resolve_path_param(:409-425) 逐字迁出, 逻辑一字不改。
    仅相对/文件名语义参数需要解析, 其余工具路径参数均为绝对路径原样返回。
    """
    if tool_name == "download" and key == "dest":
        from app.config import get_config  # 局部导入避免模块级耦合
        base = os.path.join(get_config().get_project_root(), "download")
        return os.path.abspath(os.path.join(base, value.lstrip("/\\")))
    if tool_name == "rename" and key == "dest":
        src = params.get("path") or ""
        if src:
            return str(Path(src).parent / Path(value).name)
        return value
    return value


def check_dual_permission(tool_name: str, params: Dict[str, Any]) -> SafetyResult:
    """复合工具路径检查: 源与目标各归其线逐个判定 — 小欧 2026-10-15

    2026-10-15 北京老陈裁定(真分开): 读源走读线 + 系统源外泄拦截,
    搬走源走删线, 落地目标走写线。未知档位 fail-closed 按写线。

    Args:
        tool_name: 归一化后的工具名
        params: 归一化后的工具参数

    Returns:
        SafetyResult: 全参数取最严 —— blocked 命中即返; 否则返回已暂存的 needs_confirm(取先到者);
                      全通过返 SafetyResult.pass_result()。原四元组返回已归一为单一契约。
    """
    param_map = DUAL_ACTION_PARAMS.get(tool_name)
    if param_map is None:
        # 2026-10-15 小欧 - 三堂会审: 声明为 dual 却无参数声明=配置错误, 不得静默放行。
        #   fail-closed 按写线最严处理(与 entry 未知档位同口径), 并打 warning 留痕。
        from app.logger import logger
        logger.warning(
            f"[dual_path_check] 工具 {tool_name} 声明为 dual 但 DUAL_ACTION_PARAMS 无声明, "
            f"按写线(fail-closed 最严档)处理; 请补声明表")
        hit = False
        pending_confirm: Optional[SafetyResult] = None
        for key in ("path", "dest"):
            value = params.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                continue                                # 内容型参数(非路径): 跳过
            hit = True
            real_path = resolve_path_param(tool_name, key, value, params)
            result = write_path_check.write_permission(real_path)
            if result.blocked:
                return result
            if result.needs_confirm and pending_confirm is None:
                pending_confirm = result
        if not hit:
            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_PATH_INVALID,
                                message=f"工具 {tool_name} 声明为 dual 但调用不带任何路径参数")
        return pending_confirm if pending_confirm is not None else SafetyResult.pass_result()
    pending_confirm: Optional[SafetyResult] = None
    for key, action in param_map.items():
        value = params.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            continue                                    # 内容型参数(如 generate_chart.data 内联 dict/list): 非路径
        real_path = resolve_path_param(tool_name, key, value, params)
        if action == "read":
            result = read_path_check.read_permission(real_path)
            if result.blocked:
                return result
            if result.needs_confirm and pending_confirm is None:
                pending_confirm = result
            # 系统源外泄拦截: 读线放行系统目录, 但搬运类工具不得以系统目录为数据源
            cat, msg = classify_forbidden_path(real_path, "write")
            if cat == "system":
                return SafetyResult(blocked=True, safety_level=SafetyLevel.PATH_FORBIDDEN, message=msg)
        elif action == "delete":
            # 2026-10-17 小欧 - 删除权限判定全部下沉到 delete_permission(本层纯调用, 不重判)。
            #   裁定: 补 recursive(目录=递归→R6/R4, 文件=非递归→R5/R3); move 删源 confirm **返回弹窗**
            #   (move=删源→写目标, 删源不可逆, 与单 delete 工具对齐; copy 源走读线故不涉及本分支)。
            # 2026-10-19 小欧 - needs_confirm 暂存待终判(不再即时返回): 否则"删源越界需授权"会挡住
            #   其后系统目标写的 blocked, 硬拦被降级为可授权(under-block)。全参数取最严: blocked > needs_confirm。
            _perm = delete_path_check.delete_permission(
                real_path, {"recursive": os.path.isdir(real_path)})
            if _perm.blocked:
                return _perm
            if _perm.needs_confirm and pending_confirm is None:
                pending_confirm = _perm
        else:  # write, 未知档位 fail-closed 按写线(最严)
            result = write_path_check.write_permission(real_path)
            if result.blocked:
                return result
            if result.needs_confirm and pending_confirm is None:
                pending_confirm = result

    return pending_confirm if pending_confirm is not None else SafetyResult.pass_result()