# -*- coding: utf-8 -*-
"""
编辑历史:
- 2026-07-20 小欧 新建: 从 read_text_file._select_lines 抽取共享行分页逻辑(DRY)
- 2026-07-20 小欧 修复: content 拼接由 "".join 改为 "\\n".join, 否则丢失行/段落分隔符(导致 read_text_file/read_docx roundtrip 失败)
- 2026-08-05 小欧 修复: select_lines双换行bug - splitlines(keepends=True) + "\\n".join导致空行翻倍(三堂会审Bug4)
行分页/截断工具 — 小欧 2026-07-20

#10 去噪专用: 将已完整读入内存的文本内容, 按 行号窗口(offset/limit/tail) 选取子集,
供 read_text_file / read_docx 等工具复用, 满足"按被读物自然单位翻页"的治理要求。

设计原则:
- 本模块只做"行选取", 不做任何单行字符截断 (Tool 层零限制, 字符截断唯一收口于 observation_formatter)。
- 入参 out_of_range 返回 warning 而非 error, 让上层工具决定如何呈现。
- DRY: read_text_file 的原 _select_lines 逻辑抽取至此, docx 等复用, 杜绝重造轮子。
"""

from typing import Any, Dict, Optional


def select_lines(
    lines: list,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    tail: Optional[int] = None,
) -> Dict[str, Any]:
    """按行号窗口选取并返回 _data 字典 — 小欧 2026-07-20 从 read_text_file._select_lines 抽取

    offset: 起始行号(正数, 必须配合 limit)
    limit:  读取行数
    tail:   读取尾部 N 行

    注意: lines 参数应为不带行尾换行符的列表(如 splitlines(keepends=False) 或 split("\\n"))
          避免 splitlines(keepends=True) + "\\n".join 导致空行翻倍 — 小欧 2026-08-05 三堂会审Bug4修复

    返回:
        content:      选取后的拼接文本
        total_lines:  原始总行数
        line_count:   本次选取行数
        start_line:   本次首行(1-based, 未选取为 0)
        end_line:     本次末行(1-based, 未选取为 0)
        warning:      偏移越界等提示(可选)
    """
    total = len(lines)
    params: Dict[str, Any] = {}
    warning = None

    if tail is not None:
        if total == 0:
            warning = "空文件无法使用tail参数(文件共0行)"
            selected = []
            n = 0
            params = {"tail": tail, "start_line": 0, "end_line": 0}
        else:
            start_idx = max(0, total - tail)
            selected = lines[start_idx:]
            n = len(selected)
            params = {"tail": tail, "start_line": start_idx + 1, "end_line": total}
    elif offset is not None:
        if total == 0:
            warning = "空文件无法使用offset参数(文件共0行)"
            selected = []
            n = 0
            params = {"offset": offset, "limit": limit, "start_line": 0, "end_line": 0}
        else:
            start_idx = offset - 1
            if start_idx >= total:
                warning = f"offset={offset}超出文件范围(共{total}行),返回空内容"
            selected = lines[start_idx : start_idx + limit]
            n = len(selected)
            params = {
                "offset": offset,
                "limit": limit,
                "start_line": start_idx + 1 if n > 0 else 0,
                "end_line": start_idx + n if n > 0 else 0,
            }
    elif limit is not None:
        selected = lines[:limit]
        n = len(selected)
        params = {"offset": None, "limit": limit, "start_line": 1, "end_line": n}
    else:
        selected = lines
        n = len(selected)
        params = {"start_line": 1, "end_line": n}

    content = "\n".join(selected)
    result = {
        "content": content,
        "total_lines": total,
        "line_count": len(selected),
        **params,
    }
    if warning:
        result["warning"] = warning
    return result
