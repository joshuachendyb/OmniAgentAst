# -*- coding: utf-8 -*-
"""shell_parse.parse_move — 搬移动作解析(搬移套 · ps/cmd/bash 三型动词表, 源/目标分离) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 搬移套 · ps/cmd/bash 三型动词表(源/目标分离), 独立成第四套。
2026-10-18 - 小欧 - 动词表按「套×型」重排: 本文件内含
  MOVE_VERBS_PS / MOVE_VERBS_CMD / MOVE_VERBS_BASH 三型; 并正则由 verb_table.build_verb_re 承担。
  按文本顺序有序切词(-Destination/-dest/-NewName 之后为目标, 否则首路径为源、余为目标),
  展开为「源 → delete / 目标 → write」两条动作。
2026-10-18 - 小欧 - DRY: 源/目标切分逻辑抽到 lexer.split_source_target(与复制套共用),
  本文件删私有 _pathish/_ABS_HEAD_RE, 行为逐字等价。

分层: 本文件只出动作, 不判权限。
"""
from typing import Dict, List

from app.safety.shell_parse.action import DELETE_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.verb_table import BASH, CMD, PS, build_verb_re

# ── 搬移套 · 三型动词表(单一真源) ───────────────────────────────────────
MOVE_VERBS_PS = ("Move-Item", "mi", "mv", "Rename-Item", "ren", "rnm")
MOVE_VERBS_CMD = ("move", "ren", "rename")
MOVE_VERBS_BASH = ("mv", "rename")

MOVE_VERBS_BY_SHELL: Dict[str, tuple] = {PS: MOVE_VERBS_PS, CMD: MOVE_VERBS_CMD, BASH: MOVE_VERBS_BASH}
SHELL_MOVE_RE = build_verb_re(MOVE_VERBS_BY_SHELL)

_MOVE_DEST_SWITCHES = frozenset({"-destination", "-dest", "-newname"})


def parse_move_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的搬移动作, 返回 [源 delete, 目标 write] 动作清单 — 小欧 2026-10-18

    无搬移动词 → 空清单。源/目标切分复用 lexer.split_source_target(单一真源, 与复制套共用)。
    """
    if not SHELL_MOVE_RE.search(lexer.blank_quotes(statement)):
        return []
    sources, targets = lexer.split_source_target(statement, cwd, _MOVE_DEST_SWITCHES)
    if not sources and not targets:
        return []
    actions: List[PathAction] = [PathAction(DELETE_KIND, p, {}, origin="move-src") for p in sources]
    actions += [PathAction(WRITE_KIND, p, {}, origin="move-dst") for p in targets]
    return actions


__all__ = ["parse_move_action", "SHELL_MOVE_RE", "MOVE_VERBS_PS", "MOVE_VERBS_CMD",
           "MOVE_VERBS_BASH", "MOVE_VERBS_BY_SHELL"]
