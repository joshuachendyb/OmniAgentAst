# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-13 商量 - 新建: 文件名通配模式的花括号展开单源(expand_braces)。
#   起因: fnmatch 只支持 * ? [seq], 不认 {a,b}(shell 展开特性) → LLM 写 "*.{py,ts,tsx}"
#   过滤多扩展名时必然 0 命中, 且工具层无任何报错, 表现为"明明有文件却搜不到", 极难自纠。
#   本模块只做展开(不做匹配, 保留各调用点原有大小写语义), 供 grep / find 两处共用。
"""
S: glob_pattern — 文件名通配模式的花括号展开(单源)

职责(SRP): 只做"把 {a,b} 花括号组展开为多个普通 glob 模式", **不做匹配**——匹配仍由
调用方的 fnmatch 完成, 以保留各调用点原有的大小写语义(Windows fnmatch 天然忽略大小写)。

为什么需要: fnmatch 只支持 * ? [seq], **不支持 {a,b}**(那是 shell 展开特性)。LLM 习惯写
"*.{py,ts,tsx}" 表达"多扩展名过滤", 直接交给 fnmatch 必然 0 命中 —— 工具表现为"明明有文件
却搜不到", 且无任何报错提示, 极难自纠。

用法:
    from app.utils.glob_pattern import expand_braces
    expand_braces("*.{py,ts,tsx}")  # → ["*.py", "*.ts", "*.tsx"]
    any(fnmatch.fnmatch(name, p) for p in expand_braces(pattern))
"""
from typing import List, Optional, Tuple

_MAX_EXPANDED_PATTERNS = 64   # 展开上限, 防组合爆炸({a,b}×N 组呈指数增长)

__all__ = ["expand_braces"]


def _find_group_end(text: str, start: int) -> int:
    """返回 text[start] 处 '{' 的配对 '}' 下标; 无配对返回 -1(按字面量处理)。"""
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_group(body: str) -> List[str]:
    """按顶层逗号切分花括号组内容(嵌套组不被切断)。"""
    parts: List[str] = []
    cur: List[str] = []
    depth = 0
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _find_expandable_group(pattern: str) -> Optional[Tuple[int, int, List[str]]]:
    """定位第一个"可展开"的花括号组(含顶层逗号)。返回 (start, end, parts); 无则 None。

    无逗号的组(如 "{a}")不是可展开组, 按字面量跳过继续往后找。"""
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i] != "{":
            i += 1
            continue
        end = _find_group_end(pattern, i)
        if end == -1:
            return None
        parts = _split_group(pattern[i + 1:end])
        if len(parts) > 1:
            return i, end, parts
        i = end + 1
    return None


def expand_braces(pattern: str, max_patterns: int = _MAX_EXPANDED_PATTERNS) -> List[str]:
    """展开花括号组: "*.{py,ts}" → ["*.py", "*.ts"]; 无可展开组时原样返回单元素列表。

    - 支持嵌套: "{a,{b,c}}" → ["a", "b", "c"]
    - 无逗号的组按字面量处理: "{a}" → ["{a}"]
    - 未配对的 '{' 按字面量处理, 不报错
    - 展开数超上限即截断返回(防组合爆炸), 上限 64
    """
    if not pattern or "{" not in pattern:
        return [pattern]
    found = _find_expandable_group(pattern)
    if found is None:
        return [pattern]
    start, end, parts = found
    prefix, suffix = pattern[:start], pattern[end + 1:]
    out: List[str] = []
    for part in parts:
        for sub in expand_braces(prefix + part + suffix, max_patterns):
            out.append(sub)
            if len(out) >= max_patterns:
                return out
    return out
