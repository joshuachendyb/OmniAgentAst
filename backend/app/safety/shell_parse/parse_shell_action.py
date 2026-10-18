# -*- coding: utf-8 -*-
"""shell_parse.parse_shell_action — 解析唯一入口(拆句 → 调 4 解析器 → 汇总) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.4「解析总体流水线(7 步)」落地。
  流程: [1]预处理 → [2]语句拆分 → [3][4]逐句分类+抽路径(各 parse_*) → [5]组装动作
        → [6]归一(去重 + 交集取严) → [7]输出 List[PathAction]。
  管道: 下游无路径的删/搬移段继承上游读段的产物路径(概设 §13.2.3.6, 修 B3)。

  契约: parse_shell_action(command, shell_type=None, cwd=None) -> List[PathAction]
  空清单 = 8.0(非路径动作); 单 kind = 8.1/8.2/8.3; delete+write = 8.4(搬移)。
  本层只解析、不判权限(R7 零耦合)。
2026-10-18 - 小欧 - 三堂会审回归修复: 全局早退门补 SHELL_MOVE_RE —— 沙箱宽表不含 CMD `move`/`ren`
  与 PS `Rename-Item`, 仅靠宽表会使这三类命令早退为空清单, 绕过全部路径检查(相对旧 shell_has_write_intent
  的 del/move 双表门属退化)。修复后与搬移解析器识别口径一致。
"""
from typing import List, Optional

from app.safety.shell_parse.action import DELETE_KIND, READ_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.parse_delete import SHELL_DELETE_RE, parse_delete_action
from app.safety.shell_parse.parse_move import SHELL_MOVE_RE, parse_move_action
from app.safety.shell_parse.parse_read import READ_RE, parse_read_action
from app.safety.shell_parse.parse_write import parse_write_action
from app.safety.shell_command_process import SHELL_WRITE_INTENT_RE  # 沙箱宽表仍在原模块(概设 §13.2.3.8)

# 分类优先级: 搬移 → 删 → 写 → 读(删/搬移优先取严)
_SEGMENT_PARSERS = (parse_move_action, parse_delete_action, parse_write_action, parse_read_action)


def _parse_segment(statement: str, shell: str, cwd) -> List[PathAction]:
    """按优先级把一条(管道)语句交给 4 个解析器, 首个出动作者胜出 — 小欧 2026-10-18"""
    for parser in _SEGMENT_PARSERS:
        actions = parser(statement, shell, cwd)
        if actions:
            return actions
    return []


def _normalize(actions: List[PathAction]) -> List[PathAction]:
    """[6] 归一: 去重 + 交集取严(同路径既删又写 → 归删) — 小欧 2026-10-18"""
    seen = set()
    deduped: List[PathAction] = []
    for action in actions:
        key = (action.kind, action.path.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    deleted = {a.path.lower() for a in deduped if a.kind == DELETE_KIND}
    return [a for a in deduped if not (a.kind == WRITE_KIND and a.path.lower() in deleted)]


def parse_shell_action(command: str, shell_type: Optional[str] = None,
                       cwd: Optional[str] = None) -> List[PathAction]:
    """把一条 shell 命令解析为动作清单 — 小欧 2026-10-18

    Args:
        command:    shell 命令原文
        shell_type: ps7/ps5/cmd/bash; 缺省/非法时内部自动识别
        cwd:        相对路径解析基准(缺省视为无基准, 相对路径不入清单)

    Returns:
        List[PathAction]: 动作清单(已去重、交集取严); 空清单表示无路径动作(8.0)
    """
    if not isinstance(command, str) or not command.strip():
        return []
    shell = shell_type if shell_type in lexer.SHELLS else lexer.detect_shell(command)
    text = lexer.prepare(command)
    intent = lexer.blank_quotes(text)
    # 全局早退: 无写/删/搬移动词、无重定向、无读动词 → 无任何动作(引号内字面量不算)
    # ★搬移须单独判 SHELL_MOVE_RE: 沙箱宽表(SHELL_WRITE_INTENT_RE)只收 Move-Item/mi/mv, 不含
    #   CMD `move`/`ren` 与 PS `Rename-Item` —— 仅靠宽表会漏判, 使其绕过全部路径检查(2026-10-18 小欧 回归修复)
    if not (SHELL_WRITE_INTENT_RE.search(intent) or SHELL_MOVE_RE.search(intent)
            or ">" in intent or READ_RE.search(intent)):
        return []

    actions: List[PathAction] = []
    for statement in lexer.split_statements(text):
        upstream_reads: List[str] = []
        for segment in lexer.split_pipeline(statement):
            segment_actions = _parse_segment(segment, shell, cwd)
            # 管道继承: 下游删/搬移段无显式路径时, 取上游读段产物路径为删除目标(修 B3)
            if not segment_actions and upstream_reads:
                segment_intent = lexer.blank_quotes(segment)
                if SHELL_DELETE_RE.search(segment_intent) or SHELL_MOVE_RE.search(segment_intent):
                    segment_actions = [PathAction(DELETE_KIND, p, {}, origin="pipe")
                                       for p in upstream_reads]
            for action in segment_actions:
                if action.kind == READ_KIND:
                    upstream_reads.append(action.path)
            actions.extend(segment_actions)
    return _normalize(actions)


__all__ = ["parse_shell_action"]
