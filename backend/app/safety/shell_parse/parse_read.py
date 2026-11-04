# -*- coding: utf-8 -*-
"""shell_parse.parse_read — 读动作解析(读套 · ps/cmd/bash 三型动词表) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 读套三型动词表(READ_VERBS_PS / READ_VERBS_CMD / READ_VERBS_BASH)。
2026-10-18 - 小欧 - 动词表按「套×型」重排: 本文件即读套, 内含三型动词表; 并正则/边界由公用原子
  verb_table.build_verb_re 承担(DRY)。三壳取并集识别(命令串可能内嵌他壳调用)。
  说明: `sed` 归读(纯读形态), 原地改写 `sed -i` 由写套特例接管(删/写优先于读)。

分层: 本文件只出 read 动作, 不判权限。
"""
from typing import Dict, List

from app.safety.shell_parse.action import READ_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.verb_table import BASH, CMD, PS, build_verb_re

# ── 读套 · 三型动词表(单一真源) ─────────────────────────────────────────
READ_VERBS_PS = ("Get-Content", "gc", "Get-ChildItem", "gci", "Select-String", "sls",
                 "Get-Item", "gi", "Test-Path", "Import-Csv", "Get-FileHash",
                 "Get-ItemProperty", "Get-Acl", "Resolve-Path", "type", "cat")
READ_VERBS_CMD = ("type", "dir", "findstr", "more", "where", "fc", "tree", "comp")
READ_VERBS_BASH = ("cat", "ls", "head", "tail", "grep", "less", "more", "find", "stat",
                   "wc", "sort", "awk", "sed", "od", "xxd", "md5sum", "sha256sum",
                   "file", "du", "tree", "tac", "nl", "cut", "uniq", "diff", "bat")

READ_VERBS_BY_SHELL: Dict[str, tuple] = {PS: READ_VERBS_PS, CMD: READ_VERBS_CMD, BASH: READ_VERBS_BASH}
READ_RE = build_verb_re(READ_VERBS_BY_SHELL)


def parse_read_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的读动作, 返回 read 动作清单 — 小欧 2026-10-18

    无读动词 → 空清单。读动作判定极宽(读线处处放行), 仅为显式化读路径。
    """
    if not READ_RE.search(lexer.blank_quotes(statement)):
        return []
    return [PathAction(READ_KIND, path, {}, origin="read")
            for path in lexer.extract_paths(statement, cwd)]


__all__ = ["parse_read_action", "READ_RE", "READ_VERBS_PS", "READ_VERBS_CMD",
           "READ_VERBS_BASH", "READ_VERBS_BY_SHELL"]
