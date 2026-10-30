# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: 头尾摘录抽公共实现(读取期字符复核 + 预算期行压缩共用同一套
#   比例与省略标记), 避免两处各写一份导致口径分叉 — 小欧-2026-10-30
# 2026-10-30 小欧 三堂会审修正: clip_lines 头尾分配改为"恰好 keep_lines 行"(头=(keep−1)×头/(头+尾),
#   尾=(keep−1)−头, 省略标记占 1 行) —— 原实现头尾各取比例合计仅 0.8×keep, 调用方还得反推折算,
#   且 10 行档实留 9 行; 行数按编辑器口径算(末尾换行不算新行), 摘录后补回原末尾换行 — 小欧-2026-10-30

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

# 头尾合计比例(恒>0): 把 keep_lines 按 0.6:0.2 归一分配, 两者相加恒等于 keep_lines — 小欧 2026-10-30
_HEAD_TAIL_SUM = max(1e-6, REF_HEAD_RATIO + REF_TAIL_RATIO)


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
    """按**行**头尾摘录: 结果**恰好** keep_lines 行(头尾按 REF 比例分配)。

    返回 (文本, 省略行数); 行数不足以摘录(≤ keep_lines)时原样返回且省略数为 0。
    keep_lines 是"最终可见行数", **省略标记行也算一行** —— 否则压缩后行数比目标多 1,
    调用方(预算档)再按字符估算就会超出合计上限。

    2026-10-30 小欧 三堂会审修正: 头 = (keep−1)×头/(头+尾), 尾 = (keep−1)−头, 标记占 1 行,
      两头相加 + 标记 = 恰好 keep_lines(原实现头尾各取比例, 合计只有 0.8×keep,
      调用方还得反推折算, 且 10 行档实留 9 行)。行数按编辑器口径算(末尾换行不算新行),
      摘录后补回原末尾换行。
    """
    trailing_newline = text.endswith("\n")
    lines = text.split("\n")
    if trailing_newline:
        lines = lines[:-1]
    if keep_lines < 3 or len(lines) <= keep_lines:
        # <3 行时分不出"头+标记+尾"三段, 不做摘录(调用方最低档 REF_MIN_KEEP_LINES=10)
        return text, 0
    budget = keep_lines - 1                     # 省略标记自身占一行
    head_n = max(1, int(budget * REF_HEAD_RATIO / _HEAD_TAIL_SUM))
    tail_n = max(1, budget - head_n)
    omitted = len(lines) - head_n - tail_n
    if omitted <= 0:
        return text, 0
    body = _excerpt("\n".join(lines[:head_n]), "\n".join(lines[-tail_n:]), omitted, "行")
    return (body + "\n") if trailing_newline else body, omitted
