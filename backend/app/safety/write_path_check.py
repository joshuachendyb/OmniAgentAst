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
r"""write_path_check — 写操作路径检查(写线)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

写线策略:
  一、命中 system 禁区 → 硬拦, 永不授权(磁盘根/系统敏感文件目录/系统保护目录)
  二、命中 non_system 禁区(代码目录/授权目录) → 查任务级授权, 已授权放行, 未授权拦
  三、白名单外 → 查任务级授权, 已授权放行, 未授权拦

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块 validate_write 只返回「放行/拒绝」两态; 表里的"确认"(弹窗授权)发生在**调用方**
  path_tool_safety_checker(未授权则被拒, 授权后放行), 删列还叠加 delete_safety 的 R6 层。
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

from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17 北京老陈裁定: 本函数自 path_check_common 迁 path_utils
from app.safety.path_classify_category import classify_forbidden_path
from app.safety.temp_auth import is_temp_authorized
from app.tools.tool_types import SafetyResult   # 2026-10-17 小欧 - check_write_permission 封装口返回类型

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


def check_write_permission(path: str) -> SafetyResult:
    """写线权限封装口 — 与 check_read_permission / check_delete_permission 对称 — 小欧 2026-10-17

    照搬 _check_known_risks 对写线的 category 分流(单路径):
      system      → blocked 硬拦(永不授权)
      non_system  → requires_confirmation 任务级授权(auth_path=path)
      None(白名单外) → requires_confirmation 临时授权(auth_path=path)
      合法        → 放行
    """
    _ok, _msg, _category = validate_write(path)
    if _ok:
        return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
    if _category == "system":
        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
                            severity="dangerous")
    if _category == "non_system":
        return SafetyResult(requires_confirmation=True, blocked=False,
                            message=f"该路径在受保护区域，写入需申请授权: {path}",
                            severity="risk", auth_path=path)
    return SafetyResult(requires_confirmation=True, blocked=False,
                        message=f"该路径超出允许范围，需临时授权: {path}",
                        severity="risk", auth_path=path)


__all__ = ["validate_write", "check_write_permission"]
