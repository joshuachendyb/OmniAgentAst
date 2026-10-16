# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 多动作通道。
#   承接收两类"一条调用内混着多个动作"的检查:
#     ① 6 个复合工具的源与目标分别判定(DUAL_ACTION_PARAMS 声明式派发)
#     ② 
#   补齐两处既有缺口(文档[35] §1.2.4):
#     G1 原复合工具白名单只有 compress/extract/copy/move 四个, **漏 rename**,
#        导致 rename 的 path(源)按工具级 write 判定 → 白名单外的合法源被要求临时授权(误拦合法读源)。
#        现改为声明表全列六个, 不再靠 if 链维护。
#     G2 原参数键只认 src/source_path, **不认 path/dest**, 且 edit 完全未考虑,
#        导致 copy 的 path 参数实际按 write 判定。现声明表直接给出每个参数的动作类型。
#   手法: _validate_shell_write_targets 逐字搬迁只改 import 路径, 命令解析逻辑一字不改。
# 2026-10-15 - 北京老陈裁定(真分开): 声明表全 write 是摆设, 改为源=读线+系统源外泄拦截、
#   目标=写线、move 源=删线; 单路径 edit 移出本表(改走写线); 并修复
#   LINE_BY_ACTION[action].validate 旧名残留(三线已改名, 旧调用致 6 工具全瘫)。
# 2026-10-15 - 小欧 - 三堂会审: validate_dual_path 的 param_map is None 原静默放行, 改 fail-closed(命中路径参数逐个走写线, 零命中返 False/system) + warning 留痕。
r"""dual_path_check — 双路径通道(5 个复合工具: copy/move/compress/extract/rename)
★r 前缀必需: 下方权限总表含 Windows 路径反斜杠, 无 r 会被当 \U \W 转义序列报错。

本模块判定"一次调用里多个路径动作": 源与目标各归其线。
设计要点: 参数动作类型由 DUAL_ACTION_PARAMS 声明式单源给出,
新增复合工具只改这张表, 不改判定代码(OCP)。
原 path_safe_check.py:558-560 的 if 链(白名单四个工具 + 参数键只认 src/source_path)已废弃。

权限总表(区域 × 动作 → 拒绝/确认/放行):

★★本表是**端到端视角**(用户最终看到的), **不是本模块返回值** ★★
  本模块把每个参数派给 read/write/delete 三线, 三线各自只返回「放行/拒绝」两态;
  表里的"确认"(弹窗授权)发生在**调用方** tool_safety_checker, "确认(根外递归, 来自 R6 层)"来自
  delete_safety 的 R6 工作区边界层。→ "确认"格与本文件代码对不上是**正常的**, 那是上层行为。

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
from typing import Any, Dict, Optional, Tuple
from app.safety import read_path_check, write_path_check, delete_path_check
from app.safety.path_classify_category import classify_forbidden_path  # 2026-10-15 系统源外泄拦截用


# ── 复合工具参数动作声明(单源) ──────────────────────────────────────────
# 2026-10-15 小欧 - 文档[35] 阶段三定稿(经实测回归修正):
#   源参数(path)一律按【写线】判定, 不按读线。
#   理由: 源虽只读, 但调用意图是"把数据搬离原地"(复制/移动/压缩/重命名/编辑),
#         性质等同写。若按读线判, 读线对系统目录放行 → C:\Windows\a.txt 可被
#         压缩/复制出去, 即数据外泄。
#   实测证据: 压缩/复制/编辑系统文件必须被拦(既有回归用例断言), 改读线后该拦截消失。
#   改造前的实际行为正是"全走写线" —— 原 if 链的键名白名单只列 src/source_path,
#   而这些工具的实际参数名是 path, 从未命中 → 一律落工具级 write。
#   故此处声明为 write 是**零退化**, 不是回退。
#   保留本通道而非并入写线: 让"这批工具按写线判"成为一处显式声明,
#   而非依赖"键名恰好没命中"的隐式结果。
# 2026-10-15 - 北京老陈裁定(真分开): 上述"源一律走写线"已由本次裁定取代, 原文存档不删。
# 2026-10-15 - 北京老陈裁定(真分开): 源与目标各归其线, 不得全写 write 糊弄。
#   读线放行系统目录文件(读本身无害), 故纯数据源(path)按读线判时,
#   必须另加一条显式「系统源外泄拦截」—— 否则 compress/copy 可把 C:\Windows
#   的东西搬运出去(实测 validate_read(C:\Windows\a.txt)=True)。
#   各工具语义:
#     copy/compress/extract: 源只读 → 读线 + 系统源外泄拦截; 目标落地 → 写线
#     move: 源搬走=删 → 删线(系统目录/受保护根的删本就被拦); 目标落地 → 写线
#     rename/edit: 同一对象改名改写 → 写线(与之前一致, 零退化)
DUAL_ACTION_PARAMS: Dict[str, Dict[str, str]] = {
    "copy":     {"path": "read", "dest": "write"},
    "move":     {"path": "delete", "dest": "write"},
    "compress": {"path": "read", "dest": "write"},
    "extract":  {"path": "read", "dest": "write"},
    "rename":   {"path": "write", "dest": "write"},
}

# 动作档位 → 线模块。单一真源, path_1st_legality_check 亦引用本表(2026-10-15 小欧 - P2-22 消除双份)。
LINE_BY_ACTION = {
    "read": read_path_check,
    "write": write_path_check,
    "delete": delete_path_check,
}


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


def validate_dual_path(tool_name: str, params: Dict[str, Any]
                         ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """复合工具路径检查: 源与目标各归其线逐个判定 — 小欧 2026-10-15

    2026-10-15 北京老陈裁定(真分开): 读源走读线 + 系统源外泄拦截,
    搬走源走删线, 落地目标走写线。未知档位 fail-closed 按写线。

    Args:
        tool_name: 归一化后的工具名
        params: 归一化后的工具参数

    Returns:
        (is_valid, msg, failed_path, category) 四元组, failed_path = 首个失败参数的真实路径
    """
    param_map = DUAL_ACTION_PARAMS.get(tool_name)
    if param_map is None:
        # 2026-10-15 小欧 - 三堂会审: 声明为 dual 却无参数声明=配置错误, 不得静默放行。
        #   fail-closed 按写线最严处理(与 entry 未知档位同口径), 并打 warning 留痕。
        from app.logger import logger
        logger.warning(
            f"[dual_path_check] 工具 {tool_name} 声明为 dual 但 DUAL_ACTION_PARAMS 无声明, "
            f"按写线(fail-closed 最严档)处理; 请补声明表")
        from app.tools.tool_constants import PATH_PARAM_KEYS
        hit = False
        for key in PATH_PARAM_KEYS:
            value = params.get(key)
            if value is None:
                continue
            hit = True
            real_path = resolve_path_param(tool_name, key, value, params)
            ok, err, category = write_path_check.validate_write(real_path)
            if not ok:
                return False, err, real_path, category
        if not hit:
            return False, f"工具 {tool_name} 声明为 dual 但调用不带任何路径参数", None, "system"
        return True, None, None, None    
    for key, action in param_map.items():
        value = params.get(key)
        if value is None:
            continue
        real_path = resolve_path_param(tool_name, key, value, params)
        if action == "read":
            ok, err, category = read_path_check.validate_read(real_path)
            if ok:
                # 系统源外泄拦截: 读线放行系统目录, 但搬运类工具不得以系统目录为数据源
                cat, msg = classify_forbidden_path(real_path, "write")
                if cat == "system":
                    return False, msg, real_path, cat
        elif action == "delete":
            ok, err, category = delete_path_check.validate_delete(real_path)
        else:  # write, 未知档位 fail-closed 按写线(最严)
            ok, err, category = write_path_check.validate_write(real_path)
        if not ok:
            return False, err, real_path, category

    return True, None, None, None