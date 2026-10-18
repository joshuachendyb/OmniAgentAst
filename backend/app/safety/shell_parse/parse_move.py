# -*- coding: utf-8 -*-
"""shell_parse.parse_move — 搬移动作解析(源/目标分离) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.3/§13.2.3.6「搬移」落地。
  搬移动词表最初复用 shell_command_process.SHELL_MOVE_RE 单一真源; 按**文本顺序**有序切词
  (泛抽取 shell_extract_abs_win_paths 位置序会被打乱, 故本文件自持有序切词)。
  -Destination/-dest/-NewName 之后的路径判为目标, 其余为源; 无开关时首路径为源、余为目标。
  展开为两条动作: 源 → delete(从原位抹掉), 目标 → write(可授权), 与概设一致。
2026-10-18 - 小欧 - [38] 13.2 二次迁移(老陈裁定, 按 §13.1.2 全部移入本包): 搬移动词表整体自
  shell_command_process 迁入本文件(SHELL_MOVE_RE), 词表零复制(DRY)。
2026-10-18 - 小欧 - 三堂会审 DRY: 删私有 _MOVE_TOKEN_RE(与 lexer._TOKEN_RE 逐字相同), 分词改调
  lexer.tokenize 单一真源(行为等价)。

分层: 本文件只出动作, 不判权限(R7 零耦合)。
"""
import re
from typing import List

from app.safety.shell_parse.action import DELETE_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse import lexer

# 搬移动词表(单一真源) — 2026-10-18 小欧 [38] 13.2 自 shell_command_process 迁入(老陈裁定)
SHELL_MOVE_RE = re.compile(r"(?<![a-z0-9_-])(?:Move-Item|Rename-Item|move|ren|mi|mv)(?![a-z0-9_-])",
                           re.IGNORECASE)
_MOVE_DEST_SWITCHES = frozenset({"-destination", "-dest", "-newname"})
_ABS_HEAD_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def _pathish(token: str, cwd) -> bool:
    """词条是否像路径: 盘符绝对, 或 cwd 已知时的相对路径候选 — 小欧 2026-10-18"""
    if not token or token[0] in "-/":
        return False
    if _ABS_HEAD_RE.match(token):
        return True
    return bool(cwd) and ("\\" in token or "/" in token or "." in token)


def parse_move_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的搬移动作, 返回 [源 delete, 目标 write] 动作清单 — 小欧 2026-10-18

    无搬移动词 → 空清单。
    """
    if not SHELL_MOVE_RE.search(lexer.blank_quotes(statement)):
        return []
    tokens = lexer.tokenize(statement)   # 分词复用 lexer 单一真源(2026-10-18 小欧 DRY, 原 _MOVE_TOKEN_RE 与之逐字相同)
    paths = []
    for i, token in enumerate(tokens):
        if not _pathish(token, cwd):
            continue
        absolute = lexer.to_absolute(token, cwd)
        if absolute:
            paths.append((i, absolute))
    if not paths:
        return []
    dest_idx = next((i for i, t in enumerate(tokens)
                     if t.lower() in _MOVE_DEST_SWITCHES), None)
    if dest_idx is None:
        sources = [paths[0][1]]
        targets = [p for _, p in paths[1:]]
    else:
        sources = [p for i, p in paths if i < dest_idx] or [p for _, p in paths]
        targets = [p for i, p in paths if i > dest_idx]
    actions: List[PathAction] = [PathAction(DELETE_KIND, p, {}, origin="move-src") for p in sources]
    actions += [PathAction(WRITE_KIND, p, {}, origin="move-dst") for p in targets]
    return actions


__all__ = ["parse_move_action", "SHELL_MOVE_RE"]
