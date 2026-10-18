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
2026-10-18 - 小欧 - 改名动词自搬移表拆出(北京老陈裁定), 新增 RENAME_VERBS_PS/CMD/BASH 与 SHELL_RENAME_RE:
  病根: 改名前与搬移同表, 但二者**源动作档位不同** —— 搬移源被搬走、原路径消失且数据易位 → 源=delete;
  改名只换名不搬数据、原路径消失但数据完好可回退 → 源=write。合并即致 shell 侧把 rename 当搬移硬判删线,
  与工具侧 rename 走写线不一致。改法: 动词表拆两张互不合并, parse_move_action 按 is_rename 分派源 kind 与
  origin(rename-src / move-src), 目标一律 write。拆分纯字面归类, 切词与归一化逻辑零变更。

分层: 本文件只出动作, 不判权限。
"""
from typing import Dict, List

from app.safety.shell_parse.action import DELETE_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.verb_table import BASH, CMD, PS, build_verb_re

# ── 搬移套 · 三型动词表(单一真源) ───────────────────────────────────────
# 搬移与改名**源动作档位不同**, 故动词表拆两张, 不可合并:
#   搬移(move): 源被搬走, 原路径消失, 数据易位 → 源 = delete(与 move 工具一致)
#   改名(rename): 只换名不搬数据, 原路径消失但数据完好、可回退 → 源 = write(与 rename 工具一致)
# 北京老陈裁定 2026-10-18: 二者语义不同, shell 侧判定必须与工具侧一致。
MOVE_VERBS_PS = ("Move-Item", "mi", "mv")
MOVE_VERBS_CMD = ("move",)
MOVE_VERBS_BASH = ("mv",)
RENAME_VERBS_PS = ("Rename-Item", "ren", "rnm")
RENAME_VERBS_CMD = ("ren", "rename")
RENAME_VERBS_BASH = ("rename",)

MOVE_VERBS_BY_SHELL: Dict[str, tuple] = {PS: MOVE_VERBS_PS, CMD: MOVE_VERBS_CMD, BASH: MOVE_VERBS_BASH}
RENAME_VERBS_BY_SHELL: Dict[str, tuple] = {PS: RENAME_VERBS_PS, CMD: RENAME_VERBS_CMD, BASH: RENAME_VERBS_BASH}
SHELL_MOVE_RE = build_verb_re(MOVE_VERBS_BY_SHELL)
SHELL_RENAME_RE = build_verb_re(RENAME_VERBS_BY_SHELL)

_MOVE_DEST_SWITCHES = frozenset({"-destination", "-dest", "-newname"})


def parse_move_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的搬移/改名动作, 返回 [源, 目标 write] 动作清单 — 小欧 2026-10-18

    源动作档位按动词二分(北京老陈裁定 2026-10-18, 须与工具侧一致):
      搬移动词 → 源 delete(源被搬走);  改名动词 → 源 write(只换名, 数据可回退)。
    目标一律 write(新位置落盘)。
    无搬移/改名动词 → 空清单。源/目标切分复用 lexer.split_source_target(单一真源, 与复制套共用)。
    """
    intent = lexer.blank_quotes(statement)
    is_rename = bool(SHELL_RENAME_RE.search(intent))
    is_move = bool(SHELL_MOVE_RE.search(intent))
    if not (is_rename or is_move):
        return []
    sources, targets = lexer.split_source_target(statement, cwd, _MOVE_DEST_SWITCHES)
    if not sources and not targets:
        return []
    if is_rename:
        src_kind, src_origin = WRITE_KIND, "rename-src"
    else:
        src_kind, src_origin = DELETE_KIND, "move-src"
    actions: List[PathAction] = [PathAction(src_kind, p, {}, origin=src_origin) for p in sources]
    actions += [PathAction(WRITE_KIND, p, {}, origin="move-dst") for p in targets]
    return actions


__all__ = ["parse_move_action", "SHELL_MOVE_RE", "SHELL_RENAME_RE",
           "MOVE_VERBS_PS", "MOVE_VERBS_CMD", "MOVE_VERBS_BASH",
           "RENAME_VERBS_PS", "RENAME_VERBS_CMD", "RENAME_VERBS_BASH",
           "MOVE_VERBS_BY_SHELL", "RENAME_VERBS_BY_SHELL"]
