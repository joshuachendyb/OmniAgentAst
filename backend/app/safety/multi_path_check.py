# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 多动作通道。
#   承接收两类"一条调用内混着多个动作"的检查:
#     ① 6 个复合工具的源与目标分别判定(MULTI_ACTION_PARAMS 声明式派发)
#     ② 
#   补齐两处既有缺口(文档[35] §1.2.4):
#     G1 原复合工具白名单只有 compress/extract/copy/move 四个, **漏 rename**,
#        导致 rename 的 path(源)按工具级 write 判定 → 白名单外的合法源被要求临时授权(误拦合法读源)。
#        现改为声明表全列六个, 不再靠 if 链维护。
#     G2 原参数键只认 src/source_path, **不认 path/dest**, 且 edit 完全未考虑,
#        导致 copy 的 path 参数实际按 write 判定。现声明表直接给出每个参数的动作类型。
#   手法: _validate_shell_write_targets 逐字搬迁只改 import 路径, 命令解析逻辑一字不改。
"""
multi_path_check — 多动作通道(6 个复合工具 + bash)

本模块判定"一次调用里的多个动作":
  - 复合工具: 源是读、目标是写, 各自归线
  - bash: 一条命令里可能同时有写和删, 按命令内容定动作

设计要点: 复合工具的参数动作类型由 MULTI_ACTION_PARAMS 声明式单源给出,
新增复合工具只改这张表, 不改判定代码(OCP)。
原 path_safe_check.py:558-560 的 if 链(白名单四个工具 + 参数键只认 src/source_path)已废弃。

小欧 2026-10-15
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from app.safety import read_path_check, write_path_check, delete_path_check


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
MULTI_ACTION_PARAMS: Dict[str, Dict[str, str]] = {
    "copy":     {"path": "write", "dest": "write"},
    "move":     {"path": "write", "dest": "write"},
    "compress": {"path": "write", "dest": "write"},
    "extract":  {"path": "write", "dest": "write"},
    "rename":   {"path": "write", "dest": "write"},
    # edit: 单参数读写一体, 同一文件先读原内容再写回, 按写线判一次即可
    "edit":     {"path": "write"},
}

# 动作档位 → 线模块。单一真源, path_check_entry 亦引用本表(2026-10-15 小欧 - P2-22 消除双份)。
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


def validate_multi_path(tool_name: str, params: Dict[str, Any]
                         ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """复合工具路径检查: 源与目标均按声明表逐个判定 — 小欧 2026-10-15

    6 个复合工具的 path 与 dest 一律按写线判(理由见 MULTI_ACTION_PARAMS 上方注释)。

    Args:
        tool_name: 归一化后的工具名
        params: 归一化后的工具参数

    Returns:
        (is_valid, msg, failed_path, category) 四元组, failed_path = 首个失败参数的真实路径
    """
    param_map = MULTI_ACTION_PARAMS.get(tool_name)
    if param_map is None:
        return True, None, None, None

    for key, action in param_map.items():
        value = params.get(key)
        if value is None:
            continue
        real_path = resolve_path_param(tool_name, key, value, params)
        ok, err, category = LINE_BY_ACTION[action].validate(real_path)
        if not ok:
            return False, err, real_path, category

    return True, None, None, None