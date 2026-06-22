# -*- coding: utf-8 -*-
"""
clipboard_control — 剪贴板操作(read/write)
【2026-06-22 小健】合并clipboard_read+clipboard_write为统一入口
"""

import time as _time_mod
from typing import Dict, Any, Literal

from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_CLIPBOARD


def _build_clipboard_control_llm_data(exec_code: str, duration_ms: int, action: str,
                                       char_count: int = 0, err_code: str = "", detail: str = "") -> dict:
    """clipboard_control的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"剪贴板{action}失败",
            "action": {"tool": "clipboard_control", "tool_zh": "剪贴板", "target": action, "params": {"action": action}},
            "status": {"exec_code": "error", "message": f"剪贴板{action}失败", "code": err_code or ERR_DESKTOP_CLIPBOARD, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"剪贴板{action}成功: {char_count}个字符",
        "action": {"tool": "clipboard_control", "tool_zh": "剪贴板", "target": action, "params": {"action": action}},
        "status": {"exec_code": "success", "message": f"剪贴板{action}成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {"chars": {"value": char_count, "text": f"{char_count}个"}},
    }


def _read_clipboard() -> Dict[str, Any]:
    """读取剪贴板内容(内聚) — 小健 2026-06-22"""
    try:
        import pyperclip
        text = pyperclip.paste()
        return {"text": text}
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
            return {"text": text}
        except Exception as e:
            return {"error_detail": str(e), "params": {"method": "ctypes"}}


def _write_clipboard(content: str) -> Dict[str, Any]:
    """写入内容到剪贴板(内聚) — 小健 2026-06-22"""
    try:
        import pyperclip
        pyperclip.copy(content)
        return {"content": content}
    except ImportError:
        try:
            import ctypes
            CF_TEXT = 1
            GMEM_MOVEABLE = 0x0002
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            text_bytes = content.encode('gbk') + b'\0'
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
            if h_mem == 0:
                return {"error_detail": "内存分配失败", "params": {}}
            p_mem = kernel32.GlobalLock(h_mem)
            if p_mem:
                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)
                user32.OpenClipboard(None)
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_TEXT, h_mem)
                user32.CloseClipboard()
                return {"content": content}
            else:
                kernel32.GlobalFree(h_mem)
                return {"error_detail": "内存锁定失败", "params": {}}
        except Exception as e:
            return {"error_detail": str(e), "params": {"method": "ctypes"}}


def clipboard_control(action: Literal["read", "write"], content: str = "") -> Dict[str, Any]:
    """剪贴板操作 — 小健 2026-06-22 合并read/write"""
    if action == "read":
        t0 = _time_mod.perf_counter()
        result = _read_clipboard()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if "error_detail" in result:
            llm_data = _build_clipboard_control_llm_data("error", duration_ms, "read", detail=result["error_detail"])
            return build_error(data=result, llm_data=llm_data)
        data = truncate_data_for_frontend(result)
        llm_data = _build_clipboard_control_llm_data("success", duration_ms, "read", len(result.get("text", "")))
        return build_success(data=data, llm_data=llm_data)
    elif action == "write":
        if not content:
            llm_data = _build_clipboard_control_llm_data("error", 0, "write", err_code=ERR_DESKTOP_CLIPBOARD, detail="content参数不能为空")
            return build_error(data={"error_detail": "content参数不能为空", "params": {}}, llm_data=llm_data)
        t0 = _time_mod.perf_counter()
        result = _write_clipboard(content)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if "error_detail" in result:
            llm_data = _build_clipboard_control_llm_data("error", duration_ms, "write", detail=result["error_detail"])
            return build_error(data=result, llm_data=llm_data)
        data = truncate_data_for_frontend(result)
        llm_data = _build_clipboard_control_llm_data("success", duration_ms, "write", len(content))
        return build_success(data=data, llm_data=llm_data)
    else:
        llm_data = _build_clipboard_control_llm_data("error", 0, action, err_code=ERR_DESKTOP_CLIPBOARD, detail=f"无效的action: {action}")
        return build_error(data={"error_detail": f"无效的action: {action}", "params": {"action": action}}, llm_data=llm_data)


__all__ = ["clipboard_control"]