# -*- coding: utf-8 -*-
"""shell_parse.parse_delete — 删动作解析(删套 · ps/cmd/bash 三型动词表, 含递归/强制开关) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 删套 · ps/cmd/bash 三型动词表(含递归/强制开关)。
2026-10-18 - 小欧 - 动词表按「套×型」重排: 本文件即删套, 内含
  DELETE_VERBS_PS / DELETE_VERBS_CMD / DELETE_VERBS_BASH 三型; 并正则由 verb_table.build_verb_re 承担。
  递归/强制判据(shell_has_recursive_delete / SHELL_FORCE_DELETE_RES)随动作绑定为 flags。
2026-10-18 - 小欧 - 补删动词缺口: 补 bash unlink/shred 删动词; 补不可逆批量删特例 `find ... -delete`
  (原被判纯读) 与 `robocopy /MIR|/PURGE`(镜像删除, 原无 delete 动作)。
2026-10-18 - 小欧 - 剔除重定向目标(lexer.redirect_targets), 防 `> log.txt` 误落删线。
2026-10-18 - 小欧 - 递归/强制判据收紧: `-Recurse:$false` 不再误判递归; 补 bash `rm -r`(无 -f)递归判据;
  Force 必须是开关 `-Force`, 路径名里的 "Force" 不再误设。
2026-10-18 - 小欧 - DRY: 删私有 `_has_force`(与 `shell_has_force_delete` 函数体逐字重复),
  parse_delete_action 改用公开口 `shell_has_force_delete`(单一真源)。

分层: 本文件只出 delete 动作, 不判权限。
"""
import re
from typing import Dict, List

from app.safety.shell_parse.action import DELETE_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.verb_table import BASH, CMD, PS, build_verb_re

# ── 删套 · 三型动词表(单一真源) ─────────────────────────────────────────
DELETE_VERBS_PS = ("Remove-Item", "Remove-ItemProperty", "ri", "rp", "rm", "del", "erase", "rd", "rmdir")
DELETE_VERBS_CMD = ("del", "erase", "rd", "rmdir")
DELETE_VERBS_BASH = ("rm", "rmdir", "unlink", "shred")

DELETE_VERBS_BY_SHELL: Dict[str, tuple] = {PS: DELETE_VERBS_PS, CMD: DELETE_VERBS_CMD, BASH: DELETE_VERBS_BASH}
SHELL_DELETE_RE = build_verb_re(DELETE_VERBS_BY_SHELL)

# 删套特例: 无独立删动词但确实不可逆删除: 批量删/镜像删
#   2026-10-18 小欧: `find C:\\work -name *.tmp -delete` 原被判纯读;
#   `robocopy src dst /MIR` 镜像会删除目标多余文件, 原只出 write 无 delete。
_DELETE_SPECIAL_RE = re.compile(
    r"\bfind\b[^|;&]*?\s-delete\b|\brobocopy\b[^|;&]*?\s/(?:mir|purge)\b", re.IGNORECASE)

# 递归删除类(删目录树, 抹除不可逆): 工作区外递归硬拦的判据 — 小欧 2026-10-17
SHELL_RECURSIVE_DELETE_RES = (
    # PS: Remove-Item/rm/del + -Recurse + -Force; -Recurse:$false 不算递归
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+.*?-Recurse\b(?!:\$false\b).*\b-?Force\b", re.IGNORECASE),
    # PS: Remove-Item/rm + -Recurse(排除显式 -Recurse:$false)
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*?-Recurse\b(?!:\$false\b))", re.IGNORECASE),
    # PS 字母flag: rm -rf(等价于 -Recurse -Force)
    re.compile(r"(?:Remove-Item|rm|ri|erase|del)\s+.*?-[rR][fF]\b", re.IGNORECASE),
    # PS 字母flag 分离形态: rm -r -f
    re.compile(r"(?:Remove-Item|rm|ri|erase|del)\s+.*?-[rR]\b.*?-[fF]\b", re.IGNORECASE),
    # bash: rm -r(递归删目录树, 无 -f 也算)
    re.compile(r"\brm\b.*?-[rR]\b", re.IGNORECASE),
    # CMD: del /s(递归删文件)
    re.compile(r"\bdel\b.*?/s\b", re.IGNORECASE),
    # CMD: rd /s(递归删目录)
    re.compile(r"\brd\b.*?/s\b", re.IGNORECASE),
    # CMD: rmdir /s(递归删目录)
    re.compile(r"\brmdir\b.*?/s\b", re.IGNORECASE),
    # bash: rm -rf /(递归删根路径)
    re.compile(r"\brm\b.*?-rf\s+/", re.IGNORECASE),
)

# 强制删除类(仅 Force, 非递归): 只供 shell_has_destructive_delete 使用, 不作递归判据
#   2026-10-18 小欧: Force 必须是开关(-Force), 否则路径名里的 "Force" 会误设标志。
SHELL_FORCE_DELETE_RES = (
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+.*?-Force\b", re.IGNORECASE),
    re.compile(r"\bdel\b.*?/f\b", re.IGNORECASE),
)

# 高危删除全集(递归 + 强制): shell_has_destructive_delete 的判据
SHELL_DESTRUCTIVE_DELETE_RES = SHELL_RECURSIVE_DELETE_RES + SHELL_FORCE_DELETE_RES


def shell_has_recursive_delete(command: str) -> bool:
    r"""这条命令是否含"递归删除"(删目录树) — 小欧 2026-10-17

    用途: 本模块把 recursive 随动作绑定, 最终喂入 delete_path_check.delete_permission,
          使"工作区外递归=硬拦"在 shell 通道生效。
    口径: 只认递归开关(Recurse / -rf / -r -f / del|rd|rmdir /s / rm -rf /);
          不含 Force 单开关(-Force/del /f 非递归, 应落普通确认, 不得误升为递归硬拦)。
    """
    return any(rx.search(command or "") for rx in SHELL_RECURSIVE_DELETE_RES)


def shell_has_destructive_delete(command: str) -> bool:
    r"""这条命令是不是高危删除(递归/强制/带开关) — 小欧 2026-10-16

    干什么用: 供 shell_path_check.check_shell_permission 做 fail-closed 处理:
              高危删除若解析不出任何删路径(如 `rm -rf /`, 路径提取只认 Windows 绝对路径),
              说明无从判权限, 一律硬拦 system。判据成立才拒, 不是"高危即拒"。
    口径    : 只认"删除动词 + 递归/强制/s 开关"组合; 普通 `rm C:\x` 不算(走普通删线)。
    """
    return any(rx.search(command or "") for rx in SHELL_DESTRUCTIVE_DELETE_RES)


def shell_has_force_delete(command: str) -> bool:
    """这条命令是否含强制删除开关(-Force / del /f) — 小欧 2026-10-18

    公开口: 供 parse_shell_action 管道继承的 delete 动作绑定 force 标志。
    """
    return any(rx.search(command or "") for rx in SHELL_FORCE_DELETE_RES)


def _has_delete_special(statement: str) -> bool:
    """语句是否命中不可逆删除特例(find -delete / robocopy /MIR) — 小欧 2026-10-18"""
    return bool(_DELETE_SPECIAL_RE.search(lexer.blank_quotes(statement)))


def parse_delete_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的删动作, 返回 delete 动作清单 — 小欧 2026-10-18

    无删动词且无删除特例 → 空清单。递归/强制开关随每个 delete 动作绑定。
    """
    intent = lexer.blank_quotes(statement)
    if not (SHELL_DELETE_RE.search(intent) or _has_delete_special(statement)):
        return []
    flags = {"recursive": shell_has_recursive_delete(statement),
             "force": shell_has_force_delete(statement)}
    # 2026-10-18 小欧: 重定向目标(`> log.txt`)是写动作, 不该落删线;
    #   从抽取结果中剔除, 交 _parse_segment 追加的写套动作判定。
    redirect = {p.lower() for p in lexer.redirect_targets(statement, cwd)}
    return [PathAction(DELETE_KIND, path, dict(flags), origin="delete")
            for path in lexer.extract_paths(statement, cwd)
            if path.lower() not in redirect]


__all__ = ["parse_delete_action", "SHELL_DELETE_RE", "DELETE_VERBS_PS", "DELETE_VERBS_CMD",
           "DELETE_VERBS_BASH", "DELETE_VERBS_BY_SHELL",
           "SHELL_RECURSIVE_DELETE_RES", "SHELL_FORCE_DELETE_RES", "SHELL_DESTRUCTIVE_DELETE_RES",
           "shell_has_recursive_delete", "shell_has_destructive_delete", "shell_has_force_delete"]
