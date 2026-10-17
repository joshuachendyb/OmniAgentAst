# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 读线独立文件。
#   自 path_safe_check.validate_path(:287-400) 拆出读线独有策略, 逐字搬迁不改逻辑:
#     读线特征一 (:321-322): 命中禁区 → 放行, category 原样带回给调用方做分流
#     读线特征二 (:387-391): 白名单外 → 放行
#   公共步骤(空路径/穿越/白名单匹配)交 path_check_common, 禁区分类仍调 classify_forbidden_path 并传 READ_MODE。
#   原 validate_path 及其 mode 参数已删除(文档[35] 总则四 禁止 backward), 无转发壳。
# 2026-10-15 - 小欧 - 文档[35] 阶段二: 模块 docstring 补九格契约表。
# 2026-10-15 - 小欧 - 文档[35] 收尾: 九格契约表归位 path_safe_check(单一真源), 本模块只留指向说明。
# 2026-10-15 北京老陈裁定 - 删白名单死分支: if 两支返回值一字不差, 判定零影响。
# 2026-10-15 北京老陈裁定 - validate 改名 validate_read: 三线同名, 经模块引用无法辨识线的语义。
# 2026-10-17 北京老陈裁定 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path。
# 2026-10-17 北京老陈裁定 - check_preconditions 改取自 app.utils.path_utils(迁出 path_check_common), 调用前先过空值原子 reject_reason_empty_path
r"""read_path_check — 读操作路径检查(读线)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠(C:\Users 等), 无 r 会被当 \U \W 转义序列报错。

读线策略(两条独有规则):
  一、命中禁区也放行 —— 系统目录/代码库根可读, 内容敏感性交 contentFilter 兜底
  二、白名单外也放行 —— 读不写盘, 无副作用

读线处处放行, 故【不做白名单匹配】(匹配了也不改变结果, 属无效计算)。
公共步骤(空路径/路径穿越)在 path_check_common, 禁区分类仍调
classify_forbidden_path 并传 READ_MODE, 本文件只放读线独有的策略分支。

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块 validate_read 只返回「放行/拒绝」两态; 表里的"确认"(弹窗授权)发生在**调用方**
  path_tool_safety_checker, 删列的"确认"还叠加 delete_safety 的 R6 工作区边界层。
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
  · 代码目录 = get_code_root()       判**自身 + 内部所有子级**; **父级不拦**(实测 F:\ 不命中)
  · 授权目录 = get_allowed_roots()   判**自身 + 上级祖先**; **内部不拦**(实测 授权目录\sub 不命中)
               = 用户项目根 + **授权目录** + 会话工作区(session_workspace_paths) 三个来源

★读列**除非法输入外全放行**: 本模块两条独有规则(禁区放行 + 白名单外放行), 系统凭据文件亦然 ——
  靠内容过滤兜底, 不靠路径层。但**空路径 / `..`穿越 / 异常**三类仍拒绝(实测 validate_read 返回 False)。
★白名单**写与删不同命**: 白名单内写直接放行, 删仍要确认(根外递归删除)。
★本表是禁区分类的结果说明, 规则改动须同步本表, 勿只改表。

小欧 2026-10-15 建 / 2026-10-16 老陈裁定补表+订正术语+三堂会审订正视角
"""

from typing import List, Optional, Tuple

from app.safety import path_check_common as common
from app.utils.path_utils import check_preconditions, reject_reason_empty_path  # 2026-10-17 北京老陈裁定: 本函数自 path_check_common 迁 path_utils
from app.safety.path_classify_category import classify_forbidden_path

READ_MODE = "read"


def validate_read(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """读线validate_read — 小欧 2026-10-15

    Returns:
        (is_valid, error_message, category), category ∈ {"system", "non_system", None}
        读线只在"空路径/路径穿越"两种非法输入上返回 False, 其余一律 True。
        allowed_paths 形参保留但不使用: 读线处处放行, 白名单判定无影响(见头部裁定)。
    """
    try:
        _empty = reject_reason_empty_path(file_path)   # 空值真源在原子, 本线不重复实现
        if _empty:
            return False, _empty, "system"
        pre = check_preconditions(file_path)
        if pre:
            return pre

        # 禁区分类: 读线传 READ_MODE, 系统目录在读线下判定为非禁区(放行)
        category, msg = classify_forbidden_path(file_path, READ_MODE)
        if category:
            return True, None, category          # 读线独有: 禁区放行, category 带回供调用方分流

        return True, None, None                  # 读线独有: 非禁区一律放行(含白名单外)
    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与 classify_forbidden_path 异常处理口径一致;
        #   原 category=None → T2 当"白名单外非禁区→可授权请求" → 异常/恶意路径可被 grant_temp_auth 放行(安全漏洞)
        return False, f"路径验证失败: {str(e)}", "system"


__all__ = ["validate_read"]
