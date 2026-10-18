# -*- coding: utf-8 -*-
"""shell_sandbox_tables — 沙箱越界扫描表(单一职责 · 零状态 · 零 I/O) — 小欧 2026-10-18

职责: 供沙箱预检做"越界写/删/搬移"扫描: 写意图宽表 + 重定向目标 + 越界目标形态 + 沙箱自识别 + 注册表系统动词。
      **只提供扫描词面, 不判权限、不做动作分线解析。**

编辑历史:
2026-10-18 - 小欧 - 新建(SRP): 自 shell_command_process.py 拆出"沙箱越界表"单一关注点。
  其中 SHELL_WRITE_INTENT_RE 原为手抄固定串(与 parse_write 的表重复维护), 现改由删/搬移/写
  三套动词表派生(单一真源): 词面随四套表自动同步, 新增动词只改一处即生效, 并显式含删动词。

分层: 依赖 shell_parse 四套动词表(单向); 不被 shell_parse 依赖(lexer 对其依赖已改惰性, 无环)。
"""
import re

from app.safety.shell_parse.verb_table import SHELL_KEYS, flatten_verbs
from app.safety.shell_parse.parse_delete import DELETE_VERBS_BY_SHELL
from app.safety.shell_parse.parse_move import MOVE_VERBS_BY_SHELL, RENAME_VERBS_BY_SHELL
from app.safety.shell_parse.parse_write import WRITE_VERBS_BY_SHELL


def _intent_verb_union():
    """删/搬移/改名/写 四套 × 三型 动词并集(去重保序) — 沙箱宽表词面单一真源 — 小欧 2026-10-18

    改名动词(Rename-Item/ren/rnm/rename)自搬移表拆出后**必须**并入本并集:
    宽表是沙箱侧独立的判定依据, 不经 parse_shell_action 的早退门; 漏并即等于
    改名命令不进沙箱写意图判定(实测宽表命中 Rename-Item=False 即此退化)。
    """
    merged = {}
    for tables in (DELETE_VERBS_BY_SHELL, MOVE_VERBS_BY_SHELL,
                   RENAME_VERBS_BY_SHELL, WRITE_VERBS_BY_SHELL):
        for shell in SHELL_KEYS:
            merged.setdefault(shell, [])
            merged[shell].extend(tables.get(shell, ()))
    return flatten_verbs(merged)


# 宽表把删与写混一张表, 命令含删动词时判"写", 于是删系统禁区只被判
# 「可授权的写」而非「不可授权的删」, 授权后等于放行删系统目录。故拆细表三张。
# 宽表必须保留删动词: 沙箱越界写扫描正是靠它才看得到 Remove-Item/del/rm 的目标, 移出即漏扫 = 安全退化。
# 2026-10-18 小欧: 宽表改派生(单一真源), 词面随四套表自动同步。
SHELL_WRITE_INTENT_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in _intent_verb_union()) + r")\b",
    re.IGNORECASE)
SHELL_REDIRECT_RE = re.compile(r">>?\s*\"?([^\"\r\n<>|;]+)")   # 重定向目标提取(> 与 >> 同权)
SHELL_OUTSIDE_TARGET_RE = re.compile(
    r"(?:"
    r"\b[a-z]:[\\/]"                 # 绝对盘符 C:\ D:\ / C:/ D:/ (正斜杠亦属越界写, 防逃逸)
    r"|\\\\[\w.\-]+\\"               # UNC \\host\share\
    r"|\bhk(?:lm|cu|cr|u|cc):[\\/]"  # 注册表驱动器 HKLM:/HKCU: 等
    r"|\$env:[\w]+[\\/]"             # $env:XXX\ 展开(解析前形态)
    r"|[\"']?~[\\/]"                 # ~ 家目录展开
    r")", re.IGNORECASE)
SHELL_SANDBOX_SELF_RE = re.compile(r"omniagent_sandbox", re.IGNORECASE)   # 沙箱自识别(豁免词)标识
SHELL_REGISTRY_SYSTEM_VERBS = frozenset({"reg", "reg.exe", "regedit", "regedit.exe", "setx"})


__all__ = ["SHELL_WRITE_INTENT_RE", "SHELL_REDIRECT_RE", "SHELL_OUTSIDE_TARGET_RE",
           "SHELL_SANDBOX_SELF_RE", "SHELL_REGISTRY_SYSTEM_VERBS"]
