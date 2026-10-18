# -*- coding: utf-8 -*-
"""shell_parse.parse_shell_action — 解析唯一入口(拆句 → 调 4 解析器 → 汇总) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 解析唯一入口。流程: 预处理 → 语句拆分 → 逐句分类+抽路径(各 parse_*)
  → 组装动作 → 归一(去重 + 同路径按更严者保留) → 输出 List[PathAction]。
  管道: 下游无路径的删/搬移段继承上游读段的产物路径。

  契约: parse_shell_action(command, shell_type=None, cwd=None) -> List[PathAction]
  空清单 = 无路径动作; 单 kind = 纯读/写/删; delete+write = 搬移。
  本层只解析、不判权限。
2026-10-18 - 小欧 - 全局早退门补 SHELL_MOVE_RE: 沙箱宽表不含 CMD `move`/`ren` 与 PS `Rename-Item`,
  仅靠宽表会使这三类命令早退为空清单, 绕过全部路径检查。修复后与搬移解析器识别口径一致。
2026-10-18 - 小欧 - 命中的解析器非写套但语句含重定向 `>` 时, 追加写套动作,
  使重定向目标 `> log.txt` 归写线而非落入删线(原 `Remove-Item a -Force > log.txt` 误判 log.txt 为删目标)。
2026-10-18 - 小欧 - _normalize 同路径合并加强: 同(kind,路径)重复合并 flags(append 任一真则真);
  同路径既删又读亦归删(原只消 write)。
2026-10-18 - 小欧 - 管道继承出的 delete 按下游段绑定 recursive/force;
  全局早退门显式加 SHELL_DELETE_RE, 不再依赖宽表顺带包含。
"""
from typing import List, Optional

from app.safety.shell_parse.action import DELETE_KIND, READ_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.parse_delete import (
    SHELL_DELETE_RE, parse_delete_action, shell_has_force_delete, shell_has_recursive_delete)
from app.safety.shell_parse.parse_move import SHELL_MOVE_RE, parse_move_action
from app.safety.shell_parse.parse_read import READ_RE, parse_read_action
from app.safety.shell_parse.parse_write import parse_write_action
from app.safety.shell_sandbox_tables import SHELL_WRITE_INTENT_RE  # 沙箱宽表(派生自四套动词表)

# 分类优先级: 搬移 → 删 → 写 → 读(删/搬移优先)
_SEGMENT_PARSERS = (parse_move_action, parse_delete_action, parse_write_action, parse_read_action)


def _parse_segment(statement: str, shell: str, cwd) -> List[PathAction]:
    """按优先级把一条(管道)语句交给 4 个解析器, 首个出动作者优先采用 — 小欧 2026-10-18

    2026-10-18 小欧: 若命中的解析器非写套(如删/搬移)但语句含重定向 `>`, 重定向目标是写动作,
    却不该落入删线(原 `Remove-Item a -Force > log.txt` 把 log.txt 误判删除目标)。补: 追加写套
    动作(写套已含重定向目标), 同路径冲突由 _normalize 按更严者消解(既删又写归删)。
    """
    for parser in _SEGMENT_PARSERS:
        actions = parser(statement, shell, cwd)
        if actions:
            if parser is not parse_write_action and ">" in lexer.blank_quotes(statement):
                actions = actions + parse_write_action(statement, shell, cwd)
            return actions
    return []


def _normalize(actions: List[PathAction]) -> List[PathAction]:
    """归一: 去重 + 同路径按更严者保留 — 小欧 2026-10-18

    规则: 同(kind,路径)重复合并 flags(任一为真则真); 同路径既删又写/读则写、读均归删
    (抹除最严; key 已 lower(), 故大小写不敏感去重)。
    """
    index: dict = {}
    order: List[PathAction] = []
    for action in actions:
        key = (action.kind, action.path.lower())
        kept = index.get(key)
        if kept is not None:
            for fname, val in action.flags.items():
                if val and not kept.flags.get(fname):
                    kept.flags[fname] = True
            continue
        index[key] = action
        order.append(action)
    deleted = {a.path.lower() for a in order if a.kind == DELETE_KIND}
    return [a for a in order
            if not (a.kind in (WRITE_KIND, READ_KIND) and a.path.lower() in deleted)]


def parse_shell_action(command: str, shell_type: Optional[str] = None,
                       cwd: Optional[str] = None) -> List[PathAction]:
    """把一条 shell 命令解析为动作清单 — 小欧 2026-10-18

    Args:
        command:    shell 命令原文
        shell_type: ps7/ps5/cmd/bash; 缺省/非法时内部自动识别
        cwd:        相对路径解析基准(缺省视为无基准, 相对路径不入清单)

    Returns:
        List[PathAction]: 动作清单(已去重、同路径取更严者); 空清单表示无路径动作
    """
    if not isinstance(command, str) or not command.strip():
        return []
    shell = shell_type if shell_type in lexer.SHELLS else lexer.detect_shell(command)
    text = lexer.prepare(command)
    intent = lexer.blank_quotes(text)
    # 全局早退: 无写/删/搬移动词、无重定向、无读动词 → 无任何动作(引号内字面量不算)
    # 搬移须单独判 SHELL_MOVE_RE: 沙箱宽表(SHELL_WRITE_INTENT_RE)只收 Move-Item/mi/mv, 不含
    #   CMD `move`/`ren` 与 PS `Rename-Item`, 仅靠宽表会漏判而绕过全部路径检查(2026-10-18 小欧)。
    # 删动词显式判 SHELL_DELETE_RE: 不依赖宽表"顺带包含", 删动词表变更时门不失效。
    if not (SHELL_WRITE_INTENT_RE.search(intent) or SHELL_MOVE_RE.search(intent)
            or SHELL_DELETE_RE.search(intent) or ">" in intent or READ_RE.search(intent)):
        return []

    actions: List[PathAction] = []
    for statement in lexer.split_statements(text):
        upstream_reads: List[str] = []
        for segment in lexer.split_pipeline(statement):
            segment_actions = _parse_segment(segment, shell, cwd)
            # 管道继承: 下游删/搬移段无显式路径时, 取上游读段产物路径为删除目标
            if not segment_actions and upstream_reads:
                segment_intent = lexer.blank_quotes(segment)
                if SHELL_DELETE_RE.search(segment_intent) or SHELL_MOVE_RE.search(segment_intent):
                    # 2026-10-18 小欧: 继承出的 delete 原 flags 全空, 使递归属性被绕过;
                    #   按下游段文本绑定 recursive/force, 与 parse_delete_action 同口径。
                    pipe_flags = {"recursive": shell_has_recursive_delete(segment),
                                  "force": shell_has_force_delete(segment)}
                    segment_actions = [PathAction(DELETE_KIND, p, dict(pipe_flags), origin="pipe")
                                       for p in upstream_reads]
            for action in segment_actions:
                if action.kind == READ_KIND:
                    upstream_reads.append(action.path)
            actions.extend(segment_actions)
    return _normalize(actions)


__all__ = ["parse_shell_action"]
