# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 删线独立文件。
#   自 path_safe_check.validate_path(:287-400) 拆出删线独有策略, 逐字搬迁不改逻辑:
#     删线特征 (:325-328): 命中禁区(system 与 non_system 一律) → 硬拦, **无授权分支**
#     删线白名单外 (:392-395): 与写线同, 查任务级授权
#   公共步骤(空路径/穿越/白名单匹配)交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 DELETE_MODE。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 文档[35] 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 文档[35] 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 北京老陈裁定 - validate 改名 validate_delete: 三线同名, 经模块引用无法辨识线的语义。
r"""delete_path_check — 删操作路径检查(删线)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

删线策略:
  一、命中禁区 → 一律硬拦, 无授权分支(system 与 non_system 同等待遇)
  二、白名单外 → 查任务级授权(与写线同)

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块 validate_delete 只返回「放行/拒绝」两态(实测 白名单内直接放行, 无确认分支);
  表里的"确认"(弹窗授权)发生在**调用方** tool_safety_checker, 白名单内的"确认(根外递归, 来自 R6 层)"
  更来自 **delete_safety 的 R6 工作区边界层**, 不在本文件。
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

★删线比写线严: 两个 non_system 类(代码目录/授权目录)对删**一律硬拦不授权**(抹除不可逆)。
★但白名单外**不是**直接拒绝 —— 经任务级临时授权后**放行**(见 validate_delete 末段 is_temp_authorized);
  "确认"那一步在调用方, 不在本模块。
★本表是禁区分类的结果说明, 规则改动须同步本表, 勿只改表。

公共步骤(空路径/穿越/白名单匹配)在 path_check_common, 禁区分类仍调
classify_forbidden_path 并传 DELETE_MODE, 本文件只放删线独有的策略分支。

删线之外还有一层更深的防线在工作区边界(R6: 禁止删除工作区外目录递归),
不在本模块 —— 那是 delete 工具专属差异层, 判的是"工作区边界"而非"路径权限",
职责不同故分属两个文件。



九格契约表(读/写/删 × 各类区域)见同包 path_classify_category 模块头 ——
本模块只负责本线实现, 契约表单一真源, 不在此重复维护(改一处三线皆知)。

小欧 2026-10-15
"""

from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.safety.path_classify_category import classify_forbidden_path
from app.safety.temp_auth import is_temp_authorized

DELETE_MODE = "delete"


def validate_delete(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """删线validate_delete — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        命中禁区时 category 原样带回, 供调用方按 system/non_system 分流。
    """
    try:
        pre = common.check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 删线传 DELETE_MODE
        category, msg = classify_forbidden_path(file_path, DELETE_MODE)
        if category:
            return False, msg, category                          # 删线独有: 禁区一律硬拦, 无授权分支

        paths = common.resolve_allowed_paths(allowed_paths)
        if common.check_whitelist(file_path, paths):
            return True, None, None
        if is_temp_authorized(file_path):
            return True, None, None
        return False, f"路径 '{file_path}' 不在允许的操作范围内(仅允许:{', '.join(str(p) for p in paths[:5])}...)", None
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与 classify_forbidden_path 异常处理口径一致
        return False, f"路径验证失败: {str(e)}", "system"


__all__ = ["validate_delete"]
