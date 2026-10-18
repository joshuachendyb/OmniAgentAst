# -*- coding: utf-8 -*-
"""shell_parse.parse_read — 读动作解析(三壳并集) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.6「读」行动词表落地。
  覆盖 PowerShell(Get-Content/gc/Get-ChildItem/gci/Select-String/sls/Get-Item/gi/type/cat) /
  CMD(type/dir/findstr/more) / bash(cat/ls/head/tail/grep/less/find/stat)。
  识别取三壳并集(命令串可能内嵌他壳调用), 判动词在涂空引号文本上做(防模式字面量误判)。

分层: 本文件只出 read 动作, 不判权限(R7 零耦合)。
"""
import re
from typing import List

from app.safety.shell_parse.action import READ_KIND, PathAction
from app.safety.shell_parse import lexer

_READ_PS = ("Get-Content", "gc", "Get-ChildItem", "gci", "Select-String", "sls",
            "Get-Item", "gi", "Test-Path", "type", "cat")
_READ_CMD = ("type", "dir", "findstr", "more", "where")
_READ_BASH = ("cat", "ls", "head", "tail", "grep", "less", "find", "stat")

READ_RE = re.compile(
    r"(?<![a-z0-9_-])(?:" + "|".join(re.escape(v) for v in
                                     (_READ_PS + _READ_CMD + _READ_BASH)) + r")(?![a-z0-9_-])",
    re.IGNORECASE)


def parse_read_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的读动作, 返回 read 动作清单 — 小欧 2026-10-18

    无读动词 → 空清单。读动作判定极宽(读线处处放行), 仅为 8.1 显式化读路径。
    """
    if not READ_RE.search(lexer.blank_quotes(statement)):
        return []
    actions: List[PathAction] = []
    for path in lexer.extract_paths(statement, cwd):
        actions.append(PathAction(READ_KIND, path, {}, origin="read"))
    return actions


__all__ = ["parse_read_action", "READ_RE"]
