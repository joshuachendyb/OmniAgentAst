# -*- coding: utf-8 -*-
"""shell_parse.parse_write — 写动作解析(三壳并集, 含重定向) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.6「写」行动词表落地。
  写动词表最初复用 shell_command_process.SHELL_WRITE_RE 单一真源(DRY, 且受正则基线护栏锁死);
  重定向 > / >> 的目的一律归写线(概设裁定)。flags: append(>>) / wildcard(* ?)。
2026-10-18 - 小欧 - [38] 13.2 二次迁移(老陈裁定, 按 §13.1.2 全部移入本包): 写动词表整体自
  shell_command_process 迁入本文件(SHELL_WRITE_RE 及私有 _SHELL_WRITE_VERBS), 词表零复制(DRY)。
2026-10-18 - 小欧 - 三堂会审整改: 写动词表补 CMD 复制族(copy/xcopy/robocopy, 原仅 PS 别名);
  append 标志改取涂空引号文本(intent), 与 _has_redirect 同口径, 防引号内 ">>" 误设。

分层: 本文件只出 write 动作, 不判权限(R7 零耦合)。
"""
import re
from typing import List

from app.safety.shell_parse.action import WRITE_KIND, PathAction
from app.safety.shell_parse import lexer

# 纯写动词表(单一真源) — 2026-10-18 小欧 [38] 13.2 自 shell_command_process 迁入(老陈裁定)
# 有意裁剪: move 族归 SHELL_MOVE_RE(源删/目标写); del 族归 SHELL_DELETE_RE。
# 重定向 > 与 >> 不在本表: 目标恒为文件, 由 _has_redirect 单列覆盖。
# 2026-10-18 小欧 - 三堂会审补 CMD 复制族(copy/xcopy/robocopy): 原表只收 PS(Copy-Item/cp/cpi),
#   CMD `copy C:\Windows\.. C:\..` 无任何动词命中 → 系统源外泄/系统目标写均无检查(预存缺口)。
_SHELL_WRITE_VERBS = (r"(?:Copy-Item|cp|cpi|copy|xcopy|robocopy|New-Item|ni|Set-Content|Add-Content|ac|Out-File"
                      r"|Expand-Archive|reg(?:\.exe)?(?=\s|$)|setx|regedit(?:\.exe)?(?=\s|$))")
SHELL_WRITE_RE = re.compile(r"\b" + _SHELL_WRITE_VERBS + r"\b", re.IGNORECASE)


def _has_redirect(statement: str) -> bool:
    """语句是否含重定向写(> 或 >>, 在涂空引号文本上判, 排除引号内字面量)"""
    return ">" in lexer.blank_quotes(statement)


def parse_write_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的写动作, 返回 write 动作清单 — 小欧 2026-10-18

    无写动词且无重定向 → 空清单。重定向与写动词同权(概设 §13.2.3.6)。
    """
    intent = lexer.blank_quotes(statement)
    if not (SHELL_WRITE_RE.search(intent) or _has_redirect(statement)):
        return []
    append = ">>" in intent   # 2026-10-18 小欧 三堂会审: 与 _has_redirect 同口径(涂空引号), 防引号内 ">>" 误设
    actions: List[PathAction] = []
    for path in lexer.extract_paths(statement, cwd):
        wildcard = ("*" in path) or ("?" in path)
        actions.append(PathAction(WRITE_KIND, path,
                                  {"append": append, "wildcard": wildcard},
                                  origin="write"))
    return actions


__all__ = ["parse_write_action", "SHELL_WRITE_RE"]
