# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段一 新建: 写线独立文件。自 path_safe_check.validate_path(:287-400) 拆出写线独有策略, 逐字搬迁不改逻辑(特征一 :323-324 命中 system 禁区→硬拦永不授权; 特征二 :325-333 命中 non_system 禁区→查任务级授权, 无授权则拦; 特征三 :392-395 白名单外→查任务级授权, 无授权则拦); 公共步骤交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 WRITE_MODE。原 validate_path 及 mode 参数已删除(禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 北京老陈裁定 - validate 改名 validate_write: 三线同名, 经模块引用无法辨识线的语义。
# 2026-10-17 北京老陈裁定 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path
# 2026-10-17 - 小欧 - 基础归一化: 新增 check_write_permission(path) 封装口, 三线统一返回 SafetyResult(签名按各线所需: 仅删线需 params.recursive), 供确认段统一消费。
# 2026-10-17 - 小欧 - 死参清理(方案A): 删 check_write_permission 的 params 死参(写线不用 params)。
# 2026-10-17 - 小欧 - 口径对齐: blocked(系统禁区)分支删去 auth_path=path(硬拦结果无可授权语义, auth_path 定义=白名单外临时授权路径); 与 read/router/delete 的 blocked 口径一致。
# 2026-10-18 - 小欧 - [38]§12.4 落地(字面9步): 原单路径口 check_write_permission(path) 更名 write_permission(path)(供 dual/shell 复用);
#   新增工具级 check_write_permission(tool_name, params), 遍历参数经 common.check_tool_paths 逐条走 write_permission, 供 router [5] 直调。
# 2026-10-18 - 小欧 - check_tool_paths 已删除: 单线写工具路径键为 path(download/screen_capture 为 dest), 工具级口直接取该键,
#   仅对 str 值做 resolve_path_param(下载落盘相对路径解析), 再走 write_permission; 空值/穿越由 validate_write 自身判。
# 2026-10-18 - 小欧 - 补【路径名契约】注释: 本安全模块只识别 path/dest 两个路径名; 要求 schema 路径参数名只能是
#   path/dest, 其余历史名仅作别名(L2 已归一到二者); 第三路径名 = 破坏契约(静默漏检)。
# 2026-10-18 - 小欧 - 随契约调整同步 + 措辞补齐: ①四个结果补 safety_level 问题来源分类(合法/受保护区/白名单外三条授权线归 path_auth、系统禁区归 forbidden_zone), 分类由本线直给而非上层反查文案; 原 severity 四处取值(safe/dangerous/risk/risk)分别与 blocked/needs_confirm 等价、属重复编码, 一并删 ②requires_confirmation 随字段改名, docstring 分流说明同步 ③受保护区写入补"临时"二字、白名单外补时效说明 —— 临时授权是任务级、任务结束自动失效, 用户须在弹窗里看到才能与会话级"信任此操作"区分。判定分支与放行条件零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
r"""write_path_check — 写操作路径检查(写线)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

写线策略:
  一、命中 system 禁区 → 硬拦, 永不授权(磁盘根/系统敏感文件目录/系统保护目录)
  二、命中 non_system 禁区(代码目录/授权目录) → 查任务级授权, 已授权放行, 未授权拦
  三、白名单外 → 查任务级授权, 已授权放行, 未授权拦

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块 validate_write 只返回「放行/拒绝」两态; 表里的"确认"(弹窗授权)发生在**调用方**
  path_tool_safety_checker(未授权则被拒, 授权后放行), 删列还叠加 delete_path_check.check_delete_risk 的 R6 层。
  → 按本表核对本文件代码时, "确认"格对不上是**正常的**, 那是上层行为。

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

★写线: system 永久拒绝; 白名单内写放行, 白名单外与两个 non_system 类均需授权(授权后放行, 未授权拒)。
★本表是禁区分类的结果说明, 规则改动须同步本表, 勿只改表。

公共步骤(空路径/穿越/白名单匹配)在 path_check_common, 禁区分类仍调
classify_forbidden_path 并传 WRITE_MODE, 本文件只放写线独有的策略分支。

小欧 2026-10-15 建 / 2026-10-16 老陈裁定补权限总表
"""

from typing import Any, Dict, List, Optional, Tuple

from app.safety import path_check_common as common
from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17 北京老陈裁定: 本函数自 path_check_common 迁 path_utils
from app.safety.path_classify_category import classify_forbidden_path
from app.safety.temp_auth import is_temp_authorized
from app.safety.safety_result import SafetyResult   # 契约: 安全层单源

WRITE_MODE = "write"


def validate_write(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """写线validate_write — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        category=None 表示"白名单外非禁区", 交调用方按策略弹授权确认。
    """
    try:
        _empty = reject_reason_empty_path(file_path)   # 空值真源在原子, 本线不重复实现
        if _empty:
            return False, _empty, "system"
        pre = check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 写线传 WRITE_MODE, 系统保护目录在写线下判定为禁区
        category, msg = classify_forbidden_path(file_path, WRITE_MODE)
        if category:
            if category == "system":
                return False, msg, "system"                       # 写线独有: system 硬拦永不授权
            if is_temp_authorized(file_path):
                return True, None, "non_system"
            return False, msg, "non_system"                       # non_system 写可任务级授权

        paths = common.resolve_allowed_paths(allowed_paths)
        if common.check_whitelist(file_path, paths):
            return True, None, None
        if is_temp_authorized(file_path):
            return True, None, None
        return False, f"路径 '{file_path}' 不在允许的操作范围内(仅允许:{', '.join(str(p) for p in paths[:5])}...)", None
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与 classify_forbidden_path 异常处理口径一致
        return False, f"路径验证失败: {str(e)}", "system"


def write_permission(path: str) -> SafetyResult:
    """写线单路径权限口 — 供 dual_path_check / shell_path_check 复用 — 小欧 2026-10-18

    写线 category 分流(单路径):
      system      → blocked 硬拦(永不授权)
      non_system  → needs_confirm 任务级授权(auth_path=path)
      None(白名单外) → needs_confirm 临时授权(auth_path=path)
      合法        → 放行
    """
    _ok, _msg, _category = validate_write(path)
    if _ok:
        return SafetyResult(blocked=False, needs_confirm=False, message="", safety_level="path_auth")
    if _category == "system":
        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
                            safety_level="forbidden_zone")
    if _category == "non_system":
        # 2026-10-18 小欧 措辞订正: ①原文"受保护区域"是系统没有的分类名, non_system 的真实口径是
        #   **代码目录自身及其内部子级** + **允许根(项目根/授权目录/会话工作区)自身及其上级祖先**;
        #   ②补"临时"二字(原句只说"需申请授权", 用户看不出这是任务级临时授权、与会话级信任是两套机制)。
        return SafetyResult(needs_confirm=True, blocked=False,
                            message=f"该路径位于代码目录或允许根目录自身，写入需申请临时授权（仅本任务有效）: {path}",
                            safety_level="path_auth", auth_path=path)
    # 2026-10-18 小欧 措辞订正: "超出允许范围"改为本模块既有口径"不在允许的操作范围内";
    #   并补时效(临时授权为任务级, 任务结束自动失效, 用户需在弹窗里看到)。
    return SafetyResult(needs_confirm=True, blocked=False,
                        message=f"该路径不在允许的操作范围内，写入需申请临时授权（仅本任务有效，任务结束自动失效）: {path}",
                        safety_level="path_auth", auth_path=path)


def check_write_permission(tool_name: str, params: Dict[str, Any]) -> SafetyResult:
    """写线工具级权限口 — 供 path_legality_router [4] 直调 — 小欧 2026-10-18

    单线写工具路径键为 path, download/screen_capture 为 dest; 直接取该键,
    仅对 str 值做 resolve_path_param(相对路径语义解析)后走 write_permission。
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
    if isinstance(value, str):
        # 惰性导入: resolve_path_param 在 dual_path_check(避免本模块↔dual 顶层环)
        from app.safety.dual_path_check import resolve_path_param
        value = resolve_path_param(tool_name, key, value, params)
    return write_permission(value)


__all__ = ["validate_write", "write_permission", "check_write_permission"]
