# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段一 新建: 多动作通道。
#   承接收两类"一条调用内混着多个动作"的检查:
#     ① 6 个复合工具的源与目标分别判定(MULTI_ACTION_PARAMS 声明式派发)
#     ② bash 命令内的写/删目标抽取(自 path_safe_check._validate_shell_write_targets :432-485 逐字迁出)
#   补齐两处既有缺口(文档[35] §1.2.4):
#     G1 原复合工具白名单只有 compress/extract/copy/move 四个, **漏 rename**,
#        导致 rename 的 path(源)按工具级 write 判定 → 白名单外的合法源被要求临时授权(误拦合法读源)。
#        现改为声明表全列六个, 不再靠 if 链维护。
#     G2 原参数键只认 src/source_path, **不认 path/dest**, 且 edit 完全未考虑,
#        导致 copy 的 path 参数实际按 write 判定。现声明表直接给出每个参数的动作类型。
#   手法: _validate_shell_write_targets 逐字搬迁只改 import 路径, 命令解析逻辑一字不改。
"""
multi_path_check — 多动作通道(6 个复合工具 + bash)

与三条线的关系: 三线(read/write/delete_path_check)判定"一个路径一次动作",
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

from app.logger import logger
from app.safety import delete_path_check, read_path_check, write_path_check
from app.tools.fundamental.shell_command_guard import (
    _DELETE_CMD_RE,
    _WRITE_CMD_RE,
    _extract_abs_win_paths,
    _resolve_env_fragment,
    mask_quoted_spans,
)

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


def validate_bash_targets(command: str, cwd: Optional[str] = None
                          ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """bash 命令里的绝对路径写/删目标, 纳入路径权限判定 — 小欧 2026-10-14

    自 path_safe_check._validate_shell_write_targets(:432-485) 逐字迁出, 逻辑一字不改。

    病根: bash 属 FUNDAMENTAL, 不经 action_kind 分派, 此前整类**不做任何路径校验**;
      实测 `del C:\\Windows\\a.txt` / `Remove-Item C:\\Windows\\a.txt` / `echo x > C:\\Windows\\a.txt`
      在"路径权限层"与"shell 危险模式层"**双双放行**, 与 system_prompts 的
      "禁止绕路用 shell 逃避安全检查"纪律相悖(prompt 仅软约束, 代码层零强制)。

    做法(KISS): **不解析 shell 语法**, 只在命中写意图时, 把命令里的绝对路径逐个交给对应线;
      返回值直接汇入 validate_tool_path 的下游分流, 故 bash 复用与 write/delete
      完全一致的 system(硬拦) / non_system(删硬拦) 语义, 不新增第二套判定(DRY)。

    检测流程:
        bash 命令
        ├─① 有写意图吗?  剥引号后匹配 _WRITE_CMD_RE(动词) 或含 ">"
        │      无 → 放行(只读命令不打扰)
        ├─② 抽绝对路径    $env:VAR 展开 → 引号区取完整 → 引号区外扫裸路径
        └─③ 逐个交对应线   ← 不是新判定, 是复用三线
               ├─ 系统区    → blocked 硬拦, 永不授权
               ├─ 非系统区  → 删硬拦 / 写需确认
               └─ 白名单外  → 需确认

    两段文本分开用(2026-10-14 三堂会审修正两个误报):
      - 判写意图用 **剥引号后** 的文本: 否则 `Select-String -Pattern "del" <路径>` 这类只读
        查询会因模式里的动词字面量被误判为写意图 → 误要求授权。
      - 抽绝对路径用 **原文**(引号区保留): 抽路径要保住含空格的完整路径。
      - 重定向判据用剥引号后是否含 `>`, 不用 _REDIRECT_RE(它的职责是"提取目标", 需保留引号;
        用它判"是否存在重定向"会漏判 `> "带空格路径"`)。

    边界: 相对路径不抽(交沙箱预检 _is_outside_write_target);
      UNC(`\\\\host\\share`, 网络共享)不在 _ABS_WIN_PATH_RES 覆盖内 —— 北京老陈 2026-10-14 裁定
      网络类不纳入本机制, 不加该正则(避免为不做的场景引入正则与误判面); 根治仍靠沙箱 Job Object 隔离。
    """
    if not isinstance(command, str):
        # 2026-10-15 小欧 - P1-15: 实测传 int 抛 AttributeError 冒泡至入口, 排查看不出是类型问题。
        return True, None, None, None
    if not command or not command.strip():
        return True, None, None, None
    # 2026-10-15 小欧 - 新发现B: cwd 决定相对路径的解析基准, 原完全不检查 ——
    #   `cd /d C:\Windows && echo x > a.txt` 里 a.txt 是相对路径, _extract_abs_win_paths 抽不到,
    #   等于绕过全部路径检查。cwd 按写线判(要在那里执行, 且相对写会落在那里)。
    if cwd:
        ok, err, cat = write_path_check.validate(cwd)
        if not ok:
            logger.warning(f"[multi_path_check] bash 工作目录越权: category={cat}, cwd={cwd}")
            return False, err, cwd, cat
    normalized = command.replace("\r\n", " ").replace("\n", " ")
    intent_src = mask_quoted_spans(normalized)
    if not _WRITE_CMD_RE.search(intent_src) and ">" not in intent_src:
        return True, None, None, None
    # 2026-10-14 小欧 - 文档[33] 4.10-1: 命令含删动词时走删线而非写线。
    #   病根: _WRITE_CMD_RE 把删与写混一张表, 删系统禁区只被判「可授权的写」, 授权后等于放行删系统目录。
    line = delete_path_check if _DELETE_CMD_RE.search(intent_src) else write_path_check
    # $env:VAR 展开后再抽, 否则 $env:TEMP\a.txt 形态抽不到(executor 已提供该展开)
    for raw_path in _extract_abs_win_paths(_resolve_env_fragment(normalized)):
        valid, err, category = line.validate(raw_path)
        if not valid:
            # 违规必须留痕: 下游 tool_safety_checker 只记 tool=bash, 没有命令原文,
            # 安全事件排查时"是哪个命令想写这个路径"查不到 —— 此处补全(小欧 2026-10-14)
            logger.warning(
                f"[multi_path_check] bash写目标越权: category={category}, "
                f"path={raw_path}, command={command.strip()[:200]}"
            )
            return False, err, raw_path, category
    return True, None, None, None


__all__ = ["MULTI_ACTION_PARAMS", "resolve_path_param", "validate_multi_path", "validate_bash_targets"]