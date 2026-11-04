# -*- coding: utf-8 -*-
"""shell_parse.verb_table — 三壳动词表构建公用原子(单一真源) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 「解析模板 = 读/写/删/搬移 四套 × ps/cmd/bash 三型」。
  各套模块(parse_read/parse_write/parse_delete/parse_move)只声明本套三型动词表常量,
  并正则、边界、并集去重等机械动作统一由本模块承担(DRY)。
  动词两侧禁出现字符集扩为 [letters digits _ . \\ / -](原仅排 [a-z0-9_-]),
  致路径名内的动词子串被误命中: `type C:\\work\\move.txt`、`...\\del.log` 被判成 delete,
  读别名 gc/gi/sls 命中路径; 路径分隔符与点号同属词内字符。
2026-10-18 - 小欧 - 删 verb_names(全 backend 零调用, 且 docstring 与实际不符: shell_sandbox_tables
  直接调 flatten_verbs), 同步移除 typing.Sequence 与 __all__ 条目。

分层: 本模块只做"动词表 → 正则"的机械构建, 不判动作、不判权限, 零 import 副作用。
"""
import re
from typing import Dict, Iterable, List, Tuple

# 三壳标识(与 lexer 的 PS7/PS5/CMD/BASH 对齐; ps7/ps5 动词同族, 归并为 PS)
PS = "ps"
CMD = "cmd"
BASH = "bash"
SHELL_KEYS: Tuple[str, ...] = (PS, CMD, BASH)

# 动词两侧禁止出现的字符集(字符类内): 字母数字下划线 + 路径分隔符 + 点号
#   路径名 `move.txt` / `del.log` / `C:\a\gc` 不得再命中动词。
_VERB_EDGE_CLASS = r"a-z0-9_.\\/-"


def flatten_verbs(per_shell: Dict[str, Iterable[str]]) -> List[str]:
    """把 {壳: 动词序列} 展平为去重保序的动词清单(ps→cmd→bash 顺序固定)"""
    out: List[str] = []
    seen = set()
    for shell in SHELL_KEYS:
        for verb in per_shell.get(shell, ()):
            low = verb.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(verb)
    return out


def build_verb_re(per_shell: Dict[str, Iterable[str]], *, edge: bool = True) -> "re.Pattern[str]":
    """三壳动词表 → 一张并集正则 — 小欧 2026-10-18

    edge=True : 词边界排路径分隔符/点号(动作识别用, 防路径名误命中)。
    edge=False: 宽松 \b 边界(沙箱宽表扫描用, 覆盖面从宽, 只增不减)。
    """
    alt = "|".join(re.escape(v) for v in flatten_verbs(per_shell))
    if edge:
        pattern = r"(?<![" + _VERB_EDGE_CLASS + r"])(?:" + alt + r")(?![" + _VERB_EDGE_CLASS + r"])"
    else:
        pattern = r"\b(?:" + alt + r")\b"
    return re.compile(pattern, re.IGNORECASE)


__all__ = ["PS", "CMD", "BASH", "SHELL_KEYS",
           "flatten_verbs", "build_verb_re"]