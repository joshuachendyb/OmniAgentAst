# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: 头尾摘录抽公共实现(读取期字符复核 + 预算期行压缩共用同一套
#   比例与省略标记), 避免两处各写一份导致口径分叉 — 小欧-2026-10-30

"""services.refs.clip — 头尾摘录(纯函数, 零 IO)

为何独立(DRY): "按 REF_HEAD_RATIO 取头 + REF_TAIL_RATIO 取尾 + 打省略标记"这套口径被两处需要:
  resolver 读取后按实际字符复核(4.6.3); budget 压缩期按行摘录(4.7.3)。
  两处各写一份必然分叉(历史上 2MB 口径已在两文件分家一次), 收口到本模块。

粒度说明: 读取期只能按字符(行数门槛挡不住"行少单行极长"), 压缩期必须按行(要保证
  最低 REF_MIN_KEEP_LINES 行可读), 故提供 clip_text / clip_lines 两个入口, 共享同一
  省略标记格式 _excerpt, 不做第二次格式化实现。
"""
from typing import Tuple

from app.constants import REF_HEAD_RATIO, REF_TAIL_RATIO


def _excerpt(head: str, tail: str, omitted: int, unit: str) -> str:
    """头 + 省略标记 + 尾。省略标记唯一格式(两入口共用, 前端/日志解析口径一致)。"""
    return f"{head}\n…[引用超长, 已省略 {omitted} {unit}]\n{tail}"


def clip_text(text: str, cap_chars: int) -> Tuple[str, int]:
    """按**字符**头尾摘录: 结果总长 ≤ cap_chars(不含省略标记)。

    返回 (文本, 省略字符数); 未超限时原样返回且省略数为 0。
    """
    if cap_chars <= 0 or len(text) <= cap_chars:
        return text, 0
    head = text[: max(1, int(cap_chars * REF_HEAD_RATIO))]
    tail = text[-max(1, int(cap_chars * REF_TAIL_RATIO)):]
    omitted = len(text) - len(head) - len(tail)
    return _excerpt(head, tail, omitted, "字符"), omitted


def clip_lines(text: str, keep_lines: int) -> Tuple[str, int]:
    """按**行**头尾摘录: 保留头 REF_HEAD_RATIO / 尾 REF_TAIL_RATIO 比例的行。

    返回 (文本, 省略行数); 行数不足以摘录(≤ keep_lines)时原样返回且省略数为 0。
    调用方(budget)负责把"目标保留行数"折算到本函数的 keep_lines。
    """
    lines = text.split("\n")
    if keep_lines <= 0 or len(lines) <= keep_lines:
        return text, 0
    head_n = max(1, int(keep_lines * REF_HEAD_RATIO))
    tail_n = max(1, int(keep_lines * REF_TAIL_RATIO))
    omitted = len(lines) - head_n - tail_n
    if omitted <= 0:
        return text, 0
    return _excerpt("\n".join(lines[:head_n]), "\n".join(lines[-tail_n:]), omitted, "行"), omitted
