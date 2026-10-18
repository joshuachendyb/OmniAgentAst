# -*- coding: utf-8 -*-
"""shell_parse.parse_write — 写动作解析(写套 · ps/cmd/bash 三型动词表, 含重定向) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 写套 · ps/cmd/bash 三型动词表(含重定向)。
2026-10-18 - 小欧 - 动词表按「套×型」重排: 本文件即写套, 内含
  WRITE_VERBS_PS / WRITE_VERBS_CMD / WRITE_VERBS_BASH 三型; 并正则由 verb_table.build_verb_re 承担。
2026-10-18 - 小欧 - 补写动词缺口: 补 curl/wget/tee/sed -i/dd/tar -x/
  Clear-Content/Invoke-WebRequest -OutFile/Set-ItemProperty 等写动词, 原表漏致这些命令解析为空清单。
  有意裁剪: move 族归搬移套; del 族归删套; 重定向 > / >> 不在本表面向文本扫(由 _has_redirect 单列覆盖)。
  `sed` 纯读形态归读套; 仅原地改写 `sed -i` 由此处特例接住(动作优先级: 写 > 读)。
2026-10-18 - 小欧 - append 标志取涂空引号文本(intent), 与 _has_redirect 同口径。
2026-10-18 - 小欧 - 复制类(cp/copy/Copy-Item/xcopy/robocopy/rsync)源原被一律当写目标,
  改为「源出 READ、目标出 WRITE」(与搬移同形, 源不被删); 源/目标切分复用 lexer.split_source_target 单一真源。

分层: 本文件只出 write 动作, 不判权限。
"""
import re
from typing import Dict, List

from app.safety.shell_parse.action import READ_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.verb_table import BASH, CMD, PS, build_verb_re

# ── 写套 · 三型动词表(单一真源) ─────────────────────────────────────────
WRITE_VERBS_PS = ("Copy-Item", "cp", "cpi", "New-Item", "ni", "Set-Content", "sc",
                  "Add-Content", "ac", "Out-File", "Expand-Archive", "Compress-Archive",
                  "Clear-Content", "clc", "Set-ItemProperty", "sp", "New-ItemProperty",
                  "Export-Csv", "Export-Clixml", "Tee-Object", "tee",
                  "Invoke-WebRequest", "iwr", "Invoke-RestMethod", "irm",
                  "Start-Transcript", "reg", "reg.exe", "setx", "regedit", "regedit.exe")
WRITE_VERBS_CMD = ("copy", "xcopy", "robocopy", "mkdir", "md", "setx",
                   "reg", "reg.exe", "regedit", "regedit.exe", "tee")
WRITE_VERBS_BASH = ("cp", "tee", "dd", "truncate", "install", "tar", "unzip", "7z",
                    "mkdir", "touch", "ln", "rsync", "wget", "curl", "gzip", "sponge")

WRITE_VERBS_BY_SHELL: Dict[str, tuple] = {PS: WRITE_VERBS_PS, CMD: WRITE_VERBS_CMD, BASH: WRITE_VERBS_BASH}
SHELL_WRITE_RE = build_verb_re(WRITE_VERBS_BY_SHELL)

# 写套特例: 无独立动词但确实写盘: sed 原地改写
#   2026-10-18 小欧: `sed -i s/a/b/ C:\\work\\f.txt` 原解析为空清单。
_WRITE_SPECIAL_RE = re.compile(r"\bsed\b[^|;&]*?\s-i\b", re.IGNORECASE)

# 写套内「复制类」: 源是"读"、目标是"写"(与搬移同形, 但源不被删) — 小欧 2026-10-18
#   2026-10-18 小欧: 原对全部路径一律出 WRITE, `cp C:\\a C:\\b` 的源 C:\\a 被误判写目标。
#   注意: 动词仍保留在 WRITE_VERBS_* 中, 使全局写意图门(SHELL_WRITE_RE)能命中本命令。
COPY_VERBS_PS = ("Copy-Item", "cp", "cpi")
COPY_VERBS_CMD = ("copy", "xcopy", "robocopy")
COPY_VERBS_BASH = ("cp", "rsync")
_COPY_VERBS_BY_SHELL: Dict[str, tuple] = {PS: COPY_VERBS_PS, CMD: COPY_VERBS_CMD, BASH: COPY_VERBS_BASH}
SHELL_COPY_RE = build_verb_re(_COPY_VERBS_BY_SHELL)
_COPY_DEST_SWITCHES = frozenset({"-destination", "-dest"})


def _has_redirect(statement: str) -> bool:
    """语句是否含重定向写(> 或 >>, 在涂空引号文本上判, 排除引号内字面量)"""
    return ">" in lexer.blank_quotes(statement)


def parse_write_action(statement: str, shell: str, cwd) -> List[PathAction]:
    """解析一条语句中的写动作, 返回 write 动作清单 — 小欧 2026-10-18

    无写动词且无重定向 → 空清单。重定向与写动词同权。
    复制类(COPY 套): 源出 READ、目标出 WRITE; 重定向目标亦补为 WRITE。
    """
    intent = lexer.blank_quotes(statement)
    if not (SHELL_WRITE_RE.search(intent) or _WRITE_SPECIAL_RE.search(intent) or _has_redirect(statement)):
        return []
    append = ">>" in intent   # 2026-10-18 小欧: 与 _has_redirect 同口径(涂空引号), 防引号内 ">>" 误设
    # 复制类: 源/目标分线(源判读, 目标判写), 不再把源当写目标
    if SHELL_COPY_RE.search(intent):
        sources, targets = lexer.split_source_target(statement, cwd, _COPY_DEST_SWITCHES)
        actions: List[PathAction] = [PathAction(READ_KIND, p, {}, origin="copy-src")
                                     for p in sources]
        actions += [PathAction(WRITE_KIND, p, {"append": append,
                                               "wildcard": ("*" in p) or ("?" in p)},
                               origin="copy-dst") for p in targets]
        covered = {p.lower() for p in sources + targets}
        if _has_redirect(statement):
            for path in lexer.extract_paths(statement, cwd):
                if path.lower() not in covered:
                    actions.append(PathAction(WRITE_KIND, path,
                                              {"append": append,
                                               "wildcard": ("*" in path) or ("?" in path)},
                                              origin="write"))
        return actions
    actions = []
    for path in lexer.extract_paths(statement, cwd):
        wildcard = ("*" in path) or ("?" in path)
        actions.append(PathAction(WRITE_KIND, path,
                                  {"append": append, "wildcard": wildcard},
                                  origin="write"))
    return actions


__all__ = ["parse_write_action", "SHELL_WRITE_RE", "SHELL_COPY_RE",
           "WRITE_VERBS_PS", "WRITE_VERBS_CMD", "WRITE_VERBS_BASH", "WRITE_VERBS_BY_SHELL",
           "COPY_VERBS_PS", "COPY_VERBS_CMD", "COPY_VERBS_BASH"]
