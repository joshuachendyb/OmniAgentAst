# -*- coding: utf-8 -*-
"""
clipboard_read — 读取剪贴板内容
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""

import time as _time_mod
from typing import Dict, Any

from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_CLIPBOARD


def _build_clipboard_read_llm_data(exec_code: str, duration_ms: int, char_count: int = 0,
                                    err_code: str = "", detail: str = "") -> dict:
    """clipboard_read的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": "剪贴板读取失败",
            "action": {"tool": "clipboard_read", "tool_zh": "剪贴板读取", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "剪贴板读取失败", "code": err_code or ERR_DESKTOP_CLIPBOARD, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"剪贴板读取成功: {char_count}个字符",
        "action": {"tool": "clipboard_read", "tool_zh": "剪贴板读取", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "剪贴板读取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {"chars": {"value": char_count, "text": f"{char_count}个"}},
    }


def clipboard_read() -> Dict[str, Any]:
    """读取剪贴板内容 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        import pyperclip
        text = pyperclip.paste()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = truncate_data_for_frontend({"text": text})
        llm_data = _build_clipboard_read_llm_data("success", duration_ms, len(text))
        return build_success(data=data, llm_data=llm_data)
    except ImportError:
        try:
            import ctypes
            CF_TEXT = 1
            user32 = ctypes.windll.user32
            user32.OpenClipboard(None)
            try:
                data_ptr = user32.GetClipboardData(CF_TEXT)
                text = ctypes.c_char_p(data_ptr).value.decode('gbk') if data_ptr else ""
            finally:
                user32.CloseClipboard()
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"text": text}
            llm_data = _build_clipboard_read_llm_data("success", duration_ms, len(text))
            return build_success(data=data, llm_data=llm_data)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_clipboard_read_llm_data("error", duration_ms, detail=str(e))
            return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["clipboard_read"]