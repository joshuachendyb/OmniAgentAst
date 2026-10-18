# -*- coding: utf-8 -*-
"""shell_parse.parse_delete — 删动作解析(三壳并集, 含递归/强制开关) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.6「删」行动词表落地。
  删动词表最初复用 shell_command_process.SHELL_DELETE_RE 单一真源(DRY, 受正则基线护栏锁死);
  递归/强制按命令级判据单一真源(shell_has_recursive_delete / SHELL_FORCE_DELETE_RES)取,
  随动作绑定为 flags(概设 §13.2.3.6, 修 B5: 修饰不再命令级全扫)。
2026-10-18 - 小欧 - [38] 13.2 二次迁移(老陈裁定, 按 §13.1.2 全部移入本包): 删动词表与递归/强制删除判据
  整体自 shell_command_process 迁入本文件(SHELL_DELETE_RE/SHELL_RECURSIVE_DELETE_RES/SHELL_FORCE_DELETE_RES/
  SHELL_DESTRUCTIVE_DELETE_RES/shell_has_recursive_delete/shell_has_destructive_delete), 词表零复制(DRY)。

分层: 本文件只出 delete 动作, 不判权限(R7 零耦合)。
"""
import re
from typing import List

from app.safety.shell_parse.action import DELETE_KIND, PathAction
from app.safety.shell_parse import lexer

# 删动词 + 递归/强制删除判据(单一真源) — 2026-10-18 小欧 [38] 13.2 自 shell_command_process 迁入(老陈裁定)
SHELL_DELETE_RE = re.compile(
    r"(?<![a-z0-9_-])(?:Remove-Item|Remove-ItemProperty|del|erase|rd|rmdir|ri|rm)(?![a-z0-9_-])",
    re.IGNORECASE)

# 递归删除类(删目录树, 抹除不可逆) —— R6(工作区外递归硬拦)的判据单一真源 — 小欧 2026-10-17
SHELL_RECURSIVE_DELETE_RES = (
    # PS: Remove-Item/rm/del + Recurse + Force
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bRecurse\b.*\bForce\b", re.IGNORECASE),
    # PS: Remove-Item/rm + Recurse(排除显式 -Recurse:$false)
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\bRecurse\b(?!:\$false\b))", re.IGNORECASE),
    # PS 字母flag: rm -rf(等价于 -Recurse -Force)
    re.compile(r"(?:Remove-Item|rm|ri|erase|del)\s+.*?-[rR][fF]\b", re.IGNORECASE),
    # PS 字母flag 分离形态: rm -r -f
    re.compile(r"(?:Remove-Item|rm|ri|erase|del)\s+.*?-[rR]\b.*?-[fF]\b", re.IGNORECASE),
    # CMD: del /s(递归删文件)
    re.compile(r"\bdel\b.*?/s\b", re.IGNORECASE),
    # CMD: rd /s(递归删目录)
    re.compile(r"\brd\b.*?/s\b", re.IGNORECASE),
    # CMD: rmdir /s(递归删目录)
    re.compile(r"\brmdir\b.*?/s\b", re.IGNORECASE),
    # bash: rm -rf /(递归删根路径)
    re.compile(r"\brm\b.*?-rf\s+/", re.IGNORECASE),
)

# 强制删除类(仅 Force, 非递归) —— 只供 shell_has_destructive_delete 兜底, **不作 R6 递归判据**
SHELL_FORCE_DELETE_RES = (
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bForce\b", re.IGNORECASE),
    re.compile(r"\bdel\b.*?/f\b", re.IGNORECASE),
)

# 高危删除全集(递归 + 强制) —— shell_has_destructive_delete 的判据
SHELL_DESTRUCTIVE_DELETE_RES = SHELL_RECURSIVE_DELETE_RES + SHELL_FORCE_DELETE_RES


def shell_has_recursive_delete(command: str) -> bool:
    r"""这条命令是否含"递归删除"(删目录树) — 小欧 2026-10-17

    用途: 本模块把 recursive 随动作绑定, 最终喂入 delete_path_check.delete_permission,
          使 R6(工作区外递归=硬拦)在 shell 通道生效。
    口径: 只认递归开关(Recurse / -rf / -r -f / del|rd|rmdir /s / rm -rf /);
          不含 Force 单开关(-Force/del /f 非递归, 应落 R5 确认, 不得误升 R6 硬拦)。
    """
    return any(rx.search(command or "") for rx in SHELL_RECURSIVE_DELETE_RES)


def shell_has_destructive_delete(command: str) -> bool:
    r"""这条命令是不是高危删除(递归/强制/带开关) — 小欧 2026-10-16

    干什么用: 供 shell_path_check.check_shell_permission 做 **fail-closed 兜底** ——
              高危删除若**解析不出任何删路径**(如 `rm -rf /`, 路径提取只认 Windows 绝对路径),
              说明无从判权限, 一律硬拦 system。**判据成立才拒, 不是"高危即拒"**。
    口径    : 只认"删除动词 + 递归/强制/s 开关"组合; 普通 `rm C:\x` 不算(走普通删线)。
    """
    return any(rx.search(command or "") for rx in SHELL_DESTRUCTIVE_DELETE_RES)


def _has_force(statement: str) -> bool:
    """语句是否带强制删除开关(仅 Force, 非递归)"""
    return any(rx.search(statement or "") for rx in SHELL_FORCE_DELETE_RES)


def parse_delete_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的删动作, 返回 delete 动作清单 — 小欧 2026-10-18

    无删动词 → 空清单。递归/强制开关随每个 delete 动作绑定(修 B5)。
    """
    if not SHELL_DELETE_RE.search(lexer.blank_quotes(statement)):
        return []
    flags = {"recursive": shell_has_recursive_delete(statement),
             "force": _has_force(statement)}
    actions: List[PathAction] = []
    for path in lexer.extract_paths(statement, cwd):
        actions.append(PathAction(DELETE_KIND, path, dict(flags), origin="delete"))
    return actions


__all__ = ["parse_delete_action", "SHELL_DELETE_RE", "SHELL_RECURSIVE_DELETE_RES",
           "SHELL_FORCE_DELETE_RES", "SHELL_DESTRUCTIVE_DELETE_RES",
           "shell_has_recursive_delete", "shell_has_destructive_delete"]
