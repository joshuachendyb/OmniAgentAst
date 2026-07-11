# -*- coding: utf-8 -*-
"""
F4: fuzzy_match — edittext模糊匹配策略链

仅用于 mode=once 的精确匹配失败后回退。mode=all/before/after 不走模糊匹配。

策略链（按顺序尝试，命中即返回）：
1. exact — 精确匹配（与现有逻辑一致）
2. escape_normalized — \\n→换行符, \\t→制表符, \\r→回车符（处理JSON序列化伪影）

非exact匹配时启用3道防护：
1. escape_drift — 检测 \\' 和 \\" 写入伪影，阻止损坏文件
2. 条件性反转义 — new_string 中 \\t/\\r 仅当文件匹配区确有对应控制字符时才转
3. 缩进对齐 — 自动调整 new_string 缩进以匹配文件实际缩进风格

小欧 2026-07-11
"""

from typing import List, Optional, Tuple


def fuzzy_find_replace(
    content: str, old_string: str, new_string: str
) -> Tuple[str, int, int, str]:
    """模糊匹配替换（仅 mode=once 使用）。

    Args:
        content: 文件原文
        old_string: 要查找的字符串
        new_string: 替换字符串

    Returns:
        (new_content, count, total_matches, error_message)
        - 成功: (修改后的内容, 1, 全文匹配总数, "")
        - 失败: (原文, 0, 0, 错误描述)
    """
    if not old_string:
        return content, 0, 0, "old_string不能为空"

    # === Strategy 1: exact ===
    idx = content.find(old_string)
    if idx >= 0:
        total = content.count(old_string)
        new_content = content[:idx] + new_string + content[idx + len(old_string):]
        return new_content, 1, total, ""

    # === Strategy 2: escape_normalized ===
    # 将 old_string 中的 \\n→换行, \\t→制表, \\r→回车 后再尝试精确匹配
    if "\\n" in old_string or "\\t" in old_string or "\\r" in old_string:
        unescaped = old_string.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
        if unescaped != old_string:
            idx = content.find(unescaped)
            if idx >= 0:
                total = content.count(unescaped)
                region = content[idx:idx + len(unescaped)]

                # 防护1: escape_drift — 检查 new_string 中 \\' 和 \\" 伪影
                drift_err = _detect_escape_drift(new_string, old_string, region)
                if drift_err:
                    return content, 0, 0, drift_err

                # 防护2: 条件性反转义 new_string 中的 \\t 和 \\r
                effective_new = _maybe_unescape_new_string(new_string, region)

                # 防护3: 缩进对齐
                adjusted_new = _reindent_replacement(region, unescaped, effective_new)

                new_content = content[:idx] + adjusted_new + content[idx + len(unescaped):]
                return new_content, 1, total, ""

    return content, 0, 0, ""


def _detect_escape_drift(
    new_string: str, old_string: str, matched_region: str
) -> Optional[str]:
    """检测 new_string 中的转义伪影。

    当 new_string 和原 old_string 都含 \\' 或 \\"，但文件匹配区不含时，
    说明是工具调用序列化引入的伪影，写入会损坏文件。
    """
    if "\\'" not in new_string and '\\"' not in new_string:
        return None

    for suspect in ("\\'", '\\"'):
        if suspect in new_string and suspect in old_string and suspect not in matched_region:
            plain = suspect[1]
            return (
                f"转义伪影: old_string和new_string都包含{suspect!r}，"
                f"但文件匹配区无此转义。请去掉反斜杠直接使用{plain!r}字符"
            )
    return None


def _maybe_unescape_new_string(new_string: str, matched_region: str) -> str:
    """条件性反转义 new_string 中的 \\t 和 \\r。

    仅当文件匹配区中确有制表符/回车符时才转换，防止破坏源码中
    合法的字面量 \\t 字符串。
    """
    if "\\t" not in new_string and "\\r" not in new_string:
        return new_string

    out = new_string
    if "\\t" in out and "\t" in matched_region:
        out = out.replace("\\t", "\t")
    if "\\r" in out and "\r" in matched_region:
        out = out.replace("\\r", "\r")
    return out


def _reindent_replacement(matched_region: str, old_string: str, new_string: str) -> str:
    """调整 new_string 缩进以对齐文件实际缩进。

    非精确匹配时调用: 计算 LLM old_string 的基准缩进与文件匹配区的基准缩进的差值，
    按差值调整 new_string 每行缩进。
    """
    if not new_string:
        return new_string

    old_first = _first_meaningful_line(old_string)
    file_first = _first_meaningful_line(matched_region)
    if old_first is None or file_first is None:
        return new_string

    old_indent = _leading_whitespace(old_first)
    file_indent = _leading_whitespace(file_first)

    if old_indent == file_indent:
        return new_string

    out_lines: List[str] = []
    for line in new_string.split("\n"):
        if not line.strip():
            out_lines.append(line)
            continue
        line_indent = _leading_whitespace(line)
        if line_indent.startswith(old_indent):
            remainder = line[len(old_indent):]
            out_lines.append(file_indent + remainder)
        else:
            out_lines.append(file_indent + line.lstrip(" \t"))
    return "\n".join(out_lines)


def _leading_whitespace(line: str) -> str:
    """返回行的前导空白（空格/制表符）"""
    i = 0
    while i < len(line) and line[i] in (" ", "\t"):
        i += 1
    return line[:i]


def _first_meaningful_line(text: str) -> Optional[str]:
    """返回 text 中有实际内容的第一行"""
    for line in text.split("\n"):
        if line.strip():
            return line
    return None
