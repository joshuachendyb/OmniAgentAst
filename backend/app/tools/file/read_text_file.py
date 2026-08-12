# -*- coding: utf-8 -*-
"""
F1: readtext — 读取文本文件

从file_tools.py拆分而来，按工具分类聚合设计 — 小欧 2026-06-22
"""
# 编辑历史:
# 2026-07-20 - 小欧 - readtext 门限治理(章11.4):
#   1. 去除 _select_lines max_line_length
#     单行截断(Tool层零限制)
#   2. 截断收口于 observation_formatter
#     OBS_READTEXT
#   3. MAX_READ_SIZE 依3.5改名
#     READTEXT_INPUT_MAX_BYTES(各tool独立)
#   4. 保留3.4硬安全网防OOM,过大拒读
# 2026-07-20 - 小欧 - 门限复查:
#   1. 删未接入 _find_similar_files 死代码
#   2. 删未用 import difflib
# 2026-07-21 - 小欧 - 入参即信任: limit 校验加 ≤1000 上限(原仅<1)
# 2026-07-23 - 小欧 - 三堂会审5bug修复: outlimit 截断信息中原文长度错误(先存_orig_len再截断)
# 2026-07-24 - 小欧 - 修复: warning summary嵌入full detail(三重重复) → 去掉detail
# 2026-07-25 - 小欧 - 截断治理: content[:100] → READTEXT_INER_CJK_SAMPLE 命名常量
# 2026-07-26 - 小欧 - OOD: 确认READTEXT_INPUT_MAX_BYTES未落地,OOM自然抛出被except捕获(同dataanalysis模式)
# 2026-07-26 - 小沈 - BugFix #3: path参数不覆盖; #5: hint传完整路径
# 2026-08-05 - 小欧 - 文档20.3处置: READTEXT_OUTLIMIT_CHARS 截断补 data["truncated"]=True + truncated_reason 标记(20.3 read_text 决策项)
# 2026-08-05 - 小欧 - 4bug修复: Bug1:total_lines统计被截断视图污染; Bug2:截断标记被编入行号; Bug3:record_read记录被截断内容; Bug4:select_lines双换行
# 2026-08-07 - 小欧 - BUG-01修复: 翻页参数(offset/limit/tail)入口强制int(), 防直接调用(readtext)绕过Pydantic schema时 float 参数引发 line_pager slice 崩溃
#   【病根】readtext(offset=1.5) 绕过 schema 验证, select_lines 收到 float → lines[start_idx:start_idx+limit] 抛 TypeError(日志09:07:09 ×2)
#   【改法】入口处 offset/limit/tail 均为 None 时跳过, 否则 int() 强转; 保持既有校验逻辑不变(无退化)
# 2026-08-09 - 小欧 - DRY合并: 本地 _try_read_file_with_encodings 与 _looks_like_mojibake 迁入公共 file_encoding.read_file_with_encodings(import别名保持调用点零改动)
#   病根: readtext/edittext 各持一份同名编码回退读取实现且行为不一致(edittext对preferred也做替换符检查, readtext对preferred直接返回)
#   方案: 合并为公共版(取增强语义: 所有编码统一替换符阈值+mojibake检查); 本文件删除本地两份, 以 read_file_with_encodings as _try_read_file_with_encodings 复用; 清理死import(asyncio/List/Tuple/READTEXT_INER_CJK_SAMPLE/get_file_encoding)
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import READTEXT_OUTLIMIT_CHARS
from app.tools.tool_constants import ERR_FILE_READ_FAILED
from app.tools.validate.file_type_checker import check_for_text_tool
from app.tools.validate.file_path_checker import hint_for_read_error  # 统一错误提示 - 小欧 2026-07-12

from app.utils.text_utils import add_line_numbers
from app.tools.toolhelper.line_pager import select_lines
from app.logger import logger
from app.tools.file.file_encoding import read_file_with_encodings as _try_read_file_with_encodings  # 小欧 2026-08-09: 本地重复实现合并入公共file_encoding
from app.tools.file.file_state import record_read


def _build_read_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", start_line: int = 1, line_count: int = 0,
    total_lines: int = 0, file_size: int = 0, detail: str = "",
    hint: str = "", encoding_name: str = "",
    user_offset: Optional[int] = None, user_limit: Optional[int] = None,
    user_tail: Optional[int] = None, user_encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """read_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-06-24 增加warning — 小沈 2026-07-05 success显示读取行范围"""
    _act_params = {"path": file_path}
    if user_offset is not None:
        _act_params["offset"] = user_offset
    if user_limit is not None:
        _act_params["limit"] = user_limit
    if user_tail is not None:
        _act_params["tail"] = user_tail
    if user_encoding:
        _act_params["encoding"] = user_encoding
    _pi = ""
    if user_offset is not None:
        _pi += f"，第{user_offset}行起"
    if user_limit is not None:
        _pi += f"，取{user_limit}行"
    if user_tail is not None:
        _pi += f"，尾部{user_tail}行"
    if encoding_name:
        _pi += f"，编码{encoding_name}"
    if exec_code == "error":
        return {
            "summary": f"读取文件{file_path}，失败",
            "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "读取失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和参数是否正确"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"读取文件{file_path}，成功,提示说明: {line_count}/{total_lines}行，{file_size}字节{_pi}",
            "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": _act_params},
            "status": {"exec_code": "warning", "message": f"读取成功但有警告: {detail}", "code": "", "detail": detail, "hint": hint if hint else "请检查offset参数是否超出文件范围"},
            "duration_ms": duration_ms,
            "metrics": {
                "lines": {"value": line_count, "text": f"{line_count}行"},
                "total_lines": {"value": total_lines, "text": f"{total_lines}行"},
                "bytes": {"value": file_size, "text": f"{file_size}字节"},
            },
        }
    end_line = start_line + line_count - 1
    if total_lines == 0:
        msg = f"文件为空" if not encoding_name else f"文件为空,编码:{encoding_name}"
        hint_text = ""
    elif line_count == 0:
        msg = "已无更多内容，当前读取结果为空"
        hint_text = "请调整offset/limit参数"
    elif line_count < total_lines:
        enc = f",编码:{encoding_name}" if encoding_name else ""
        msg = f"读取成功:第{start_line}-{end_line}行,共{total_lines}行{enc}"
        hint_text = "可使用offset+limit继续读取后续内容"
    else:
        enc = f",编码:{encoding_name}" if encoding_name else ""
        msg = f"读取成功:第{start_line}-{end_line}行,共{total_lines}行{enc}"
        hint_text = ""
    return {
        "summary": f"读取文件{file_path}，成功: {line_count}/{total_lines}行，{file_size}字节{_pi}",
        "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": _act_params},
        "status": {"exec_code": "success", "message": msg, "code": "", "detail": "", "hint": hint_text},
        "duration_ms": duration_ms,
        "metrics": {
            "lines": {"value": line_count, "text": f"{line_count}行"},
            "total_lines": {"value": total_lines, "text": f"{total_lines}行"},
            "bytes": {"value": file_size, "text": f"{file_size}字节"},
        },
    }


async def readtext(
    path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    tail: Optional[int] = None,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文本文件 — 小沈 2026-05-25 重构拆分 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 增加文件类型前置检查 — 小欧 2026-06-28 新增tail参数替代offset负数 — 小欧 2026-07-11 路径参数统一为path
    offset: 起始行号(正数，必须配合limit)
    limit: 读取行数
    tail: 读取尾部N行（不能与offset/limit同时使用）"""
    # 路径参数统一为path,桥接到内部变量file_path — 小欧 2026-07-11
    file_path = path
    # BUG-01修复: 翻页参数强制int, 防直接调用(readtext)绕过Pydantic schema时 offset=1.5 引起 slice 崩溃 — 小欧 2026-08-07
    #   日志证据: 09:07:09 line_pager.py:69 slice indices must be integers (Offset 1.5)
    if offset is not None:
        offset = int(offset)
    if limit is not None:
        limit = int(limit)
    if tail is not None:
        tail = int(tail)
    t0 = _time_mod.perf_counter()
    try:
        # 文件类型前置检查 — 小健 2026-06-24 — check_for_text_tool 内含 validate_path 存在性校验 — 小欧 2026-07-29
        is_valid, error_detail, suggested_tool = check_for_text_tool(file_path, check_content=True)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if suggested_tool:
                _hint = f"建议使用{suggested_tool}工具"
            elif suggested_tool == "":
                _hint = "请检查文件路径和文件名是否正确"
            else:
                _hint = "文件类型不匹配,请使用其他工具"
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail, hint=_hint, user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)
            return build_error(data={}, llm_data=llm_data)

        if limit is not None and (limit < 1 or limit > 1000):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"limit参数必须在1-1000之间,传入值: {limit}",
                hint="limit参数必须设置在1-1000之间",
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            return build_error(data={}, llm_data=llm_data)

        if tail is not None and tail < 1:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"tail参数不能小于1,传入值: {tail}",
                hint="tail参数不能小于1",
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            return build_error(data={}, llm_data=llm_data)

        if encoding is not None:
            try:
                "".encode(encoding)
            except LookupError:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail=f"不支持的编码: {encoding}",
                    hint="请使用正确的编码名称,如utf-8/gbk",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={}, llm_data=llm_data)

        if tail is not None:
            if offset is not None or limit is not None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="tail参数不能与offset/limit同时使用",
                    hint="tail与offset/limit参数互斥,请选择其一",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={}, llm_data=llm_data)

        if offset is not None:
            if offset < 1:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail=f"offset参数不能小于1,传入值: {offset},行号从1开始",
                    hint="offset行号从1开始",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={}, llm_data=llm_data)
            
            if limit is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail=f"offset参数必须同时提供limit参数,当前offset={offset},示例: offset=10,limit=20读取第10-29行",
                    hint="请提供limit参数配合offset",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={}, llm_data=llm_data)

        _p = Path(file_path)

        file_size = _p.stat().st_size

        content, used_encoding, error = await _try_read_file_with_encodings(_p, encoding)
        # Bug3修复: 保存原始content用于record_read — 小欧 2026-08-05 三堂会审4bug修复
        _original_content = content
        # Bug1修复: 截断前计算真实总行数(必须在if外初始化, 否则翻页/空文件场景NameError) — 小欧 2026-08-05
        _real_total_lines = len(content.splitlines()) if content else 0
        # outlimit: 仅全量读取(无翻页参数)截断, 翻页由用户参数控制
        _outlimit_truncated = False
        _outlimit_marker = ""
        if content and offset is None and limit is None and tail is None:
            _orig_len = len(content)
            if _orig_len > READTEXT_OUTLIMIT_CHARS:
                # Bug2修复: 截断标记与正文分离, 编号后再追加(避免标记被编入行号) — 小欧 2026-08-05
                content = content[:READTEXT_OUTLIMIT_CHARS]
                _outlimit_marker = f"... (内容已截断: 原文{_orig_len}字符, 保留{READTEXT_OUTLIMIT_CHARS}字符) ..."
                _outlimit_truncated = True
        if error:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error, hint=f"文件编码无法识别，请尝试指定 encoding 参数", user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)
            return build_error(data={}, llm_data=llm_data)

        lines = content.splitlines(keepends=False)
        _data = select_lines(lines, offset, limit, tail)
        _data["encoding"] = used_encoding
        # =============================================================================
        # 数据设计：line_count/total_lines 从 data pop 出，通过 llm_data.metrics 传给 summary
        # summary 示例: "读取 /path，20/200行，1024字节"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        _line_count = _data.pop("line_count", 0)
        _total_lines = _data.pop("total_lines", 0)
        # Bug1修复: 使用真实total_lines而不是截断视图的total_lines
        if _real_total_lines:
            _total_lines = _real_total_lines
        _warning = _data.pop("warning", None)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

        if _warning:
            warning_hint = ""
            if "空文件" in _warning:
                warning_hint = "文件为空,无需使用行选择参数"
            llm_data = _build_read_text_file_llm_data(
                "warning", duration_ms, file_path=file_path,
                line_count=_line_count, total_lines=_total_lines, file_size=file_size, detail=_warning,
                hint=warning_hint,
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            _data.pop("start_line", None); _data.pop("end_line", None)
            _data.pop("offset", None); _data.pop("limit", None); _data.pop("tail", None)
            _data.pop("encoding", None)
            return build_warning(data=_data, llm_data=llm_data)

        line_offset = _data.get("start_line", 1)

        llm_data = _build_read_text_file_llm_data(
            "success", duration_ms, file_path=file_path,
            start_line=line_offset, line_count=_line_count,
            total_lines=_total_lines, file_size=file_size,
            encoding_name=used_encoding or "",
            user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
        )
        raw = _data.get("content", "")
        if raw:
            # Bug2修复: 正文与截断标记分离存储, 标记不编入行号, 编号后追加 — 小欧 2026-08-05
            _data["content"] = add_line_numbers(raw, offset=line_offset)
            if _outlimit_marker:
                _data["content"] = _data["content"] + "\n" + _outlimit_marker

        _data.pop("start_line", None); _data.pop("end_line", None)
        _data.pop("offset", None); _data.pop("limit", None); _data.pop("tail", None)
        _data.pop("encoding", None)
        if _outlimit_truncated:
            _data["truncated"] = True
            _data["truncated_reason"] = f"内容超{READTEXT_OUTLIMIT_CHARS}字符已截断(原文{_orig_len}字符)"
        record_read(file_path, _original_content)

        # ---- observation_formatter route -------------------------------------------
        # branch: #2 raw str
        # trigger: "content" in data and isinstance(data["content"], str)
        # handler: inline — 直接返回 data["content"], OBS_MAX_STRING_LENGTH 截断
        # file:    observation_formatter.py:117-122
        # ------------------------------------------------------------------------------
        return build_success(data=_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"readtext failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e), hint=hint_for_read_error(e, file_path), user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)
