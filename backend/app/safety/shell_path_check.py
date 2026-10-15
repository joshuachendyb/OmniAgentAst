# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段六 新建: 自 multi_path_check 拆出 bash 通道。
#   bash 参数是单个 command 串, 与 multi(多路径参数)无关, 同处一文件名不副实。
#   逻辑逐字搬迁不改: 命令内绝对路径写/删目标抽取 → 交三线判定。
# 2026-10-15 北京老陈裁定 - 改名 shell_path_check -> shell_path_check: 判的是 shell 命令(ps/cmd/bash 三壳), 不只 bash。
"""
shell_path_check — shell 命令路径检查(通道 B)

bash 属 FUNDAMENTAL, 不经 action_kind 分派, 单独立此通道:
从命令串里摘出绝对路径写/删目标, 逐个交读/写/删三线判定。

调用方: path_check_entry.validate_tool_path 特判 normal_name=="bash" 时调本模块。
"""

from typing import List, Optional, Tuple

from app.safety import delete_path_check, write_path_check
from app.logger import logger
from app.tools.fundamental.shell_command_guard import (
    _WRITE_CMD_RE,
    _DELETE_CMD_RE,
    mask_quoted_spans,
    _resolve_env_fragment,
    _extract_abs_win_paths,
)


def validate_shell(command: str, cwd: Optional[str] = None
                  ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    if not isinstance(command, str):
        # 2026-10-15 小欧 - P1-15: 实测传 int 抛 AttributeError 冒泡至入口, 排查看不出是类型问题。
        return True, None, None, None
    if not command or not command.strip():
        return True, None, None, None
    # 2026-10-15 小欧 - 新发现B: cwd 决定相对路径的解析基准, 原完全不检查 ——
    #   `cd /d C:\Windows && echo x > a.txt` 里 a.txt 是相对路径, _extract_abs_win_paths 抽不到,
    #   等于绕过全部路径检查。cwd 按写线判(要在那里执行, 且相对写会落在那里)。
    if cwd:
        ok, err, cat = write_path_check.validate_write(cwd)
        if not ok:
            logger.warning(f"[shell_path_check] bash 工作目录越权: category={cat}, cwd={cwd}")
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
        valid, err, category = (delete_path_check.validate_delete(raw_path)
                             if line is delete_path_check else write_path_check.validate_write(raw_path))
        if not valid:
            # 违规必须留痕: 下游 tool_safety_checker 只记 tool=bash, 没有命令原文,
            # 安全事件排查时"是哪个命令想写这个路径"查不到 —— 此处补全(小欧 2026-10-14)
            logger.warning(
                f"[shell_path_check] bash写目标越权: category={category}, "
                f"path={raw_path}, command={command.strip()[:200]}"
            )
            return False, err, raw_path, category
    return True, None, None, None


__all__ = ["MULTI_ACTION_PARAMS", "resolve_path_param", "validate_multi_path", "validate_shell"]
__all__ = ["validate_shell"]
