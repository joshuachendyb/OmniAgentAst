# -*- coding: utf-8 -*-
"""
clipboard_control — 剪贴板操作(read/write)
【2026-06-22 小健】合并clipboard_read+clipboard_write为统一入口
【2026-07-21 小欧】加 CLIPBOARD_INPUT_MAX_CHARS 截断防 OOM
【2026-07-23 小欧】_read_clipboard pyperclip.paste()异常降级到ctypes fallback, 防traceback打印
  修改原理: 原代码pyperclip.paste()抛出的任何异常直接穿透到上层, 导致traceback打印到日志。
  修改逻辑: pyperclip.paste()包try/except, 异常静默降级到ctypes fallback方案。
   注意: _read(读)做了降级, _write(写)pyperclip.copy()失败写warning日志后降级到ctypes(ctypes也失败时error返回给用户感知)。
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
# 2026-07-30 - 小欧 - #15:函数签名content:str→Optional[str],补充import; #17:llm_data params补content
# 2026-07-30 - 小欧 - #31/#36:ctypes写编码GBK→UTF-16LE统一对齐读端CF_UNICODETEXT; #32:pyperclip.copy失败加warning日志
# 2026-07-30 - 小欧 - #1:修复GMEM_MOVEABLE未定义导致ctypes fallback路径NameError崩溃
# 2026-07-31 - 小欧 - 三堂会审修复B15:OpenClipboard返回值未检查(read/write两路径),失败返回错误而非静默空文本/误报成功
# 2026-07-31 - 小欧 - 三堂会审修复B4:SetClipboardData成功后剪贴板接管内存,owned=False防CloseClipboard异常时double-free
# 2026-07-31 - 小欧 - 三堂会审修复B10:截断后char_count原为截断长度+标记,改报原始长度original_len
# 2026-07-31 - 小欧 - 三堂会审修复B26:read路径pyperclip.paste失败补warning日志与write路径对齐
import ctypes
import time as _time_mod
from typing import Dict, Any, Literal, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_DESKTOP_CLIPBOARD, CLIPBOARD_INPUT_MAX_CHARS
from app.logger import logger


def _build_clipboard_control_llm_data(exec_code: str, duration_ms: int, action: str,
                                       char_count: int = 0, content: Optional[str] = None,
                                       err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """clipboard_control的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    _act_params = {"action": action}
    if content:
        _act_params["content"] = content
    if exec_code == "error":
        return {
            "summary": f"剪贴板{action}失败",
            "action": {"tool": "clipboard_control", "tool_zh": "剪贴板", "target": action, "params": _act_params},
            "status": {"exec_code": "error", "message": f"剪贴板{action}失败", "code": err_code or ERR_DESKTOP_CLIPBOARD, "detail": detail, "hint": hint if hint else "请检查剪贴板访问权限"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"剪贴板{action}成功: {char_count}个字符",
        "action": {"tool": "clipboard_control", "tool_zh": "剪贴板", "target": action, "params": _act_params},
        "status": {"exec_code": "success", "message": f"剪贴板{action}成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {"chars": {"value": char_count, "text": f"{char_count}个"}},
    }


def _read_clipboard() -> Dict[str, Any]:
    """读取剪贴板内容(内聚) — 小健 2026-06-22
    【2026-07-23 小欧】pyperclip.paste()抛异常时降级到ctypes fallback，防traceback打印到日志"""
    try:
        import pyperclip
        try:
            text = pyperclip.paste()
            return {"text": text}
        except Exception:
            logger.warning("[clipboard_control] pyperclip.paste失败,降级到ctypes fallback")
    except ImportError:
        pass
    try:
        CF_UNICODETEXT = 13
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        if not user32.OpenClipboard(None):
            return {"error_detail": "打开剪贴板失败(可能被其他程序占用)", "params": {"method": "ctypes"}}
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    text = ctypes.wstring_at(ptr)
                    kernel32.GlobalUnlock(handle)
                else:
                    text = ""
            else:
                text = ""
        finally:
            user32.CloseClipboard()
        return {"text": text}
    except Exception as e:
        return {"error_detail": str(e), "params": {"method": "ctypes"}}


def _write_clipboard(content: str) -> Dict[str, Any]:
    """写入内容到剪贴板(内聚) — 小健 2026-06-22
    【2026-07-23 小欧】pyperclip.copy()抛异常时降级到ctypes fallback，与_read_clipboard对齐"""
    try:
        import pyperclip
        try:
            pyperclip.copy(content)
            return {"text": content}
        except Exception:
            logger.warning("[clipboard_control] pyperclip.copy失败,降级到ctypes fallback")
    except ImportError:
        pass
    try:
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        text_bytes = (content + '\0').encode('utf-16-le')
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
        if h_mem == 0:
            return {"error_detail": "内存分配失败", "params": {}}
        owned = True
        try:
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                kernel32.GlobalFree(h_mem)
                return {"error_detail": "内存锁定失败", "params": {}}
            try:
                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
            finally:
                kernel32.GlobalUnlock(h_mem)
            if not user32.OpenClipboard(None):
                kernel32.GlobalFree(h_mem)
                return {"error_detail": "打开剪贴板失败(可能被其他程序占用)", "params": {"method": "ctypes"}}
            try:
                user32.EmptyClipboard()
                if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                    kernel32.GlobalFree(h_mem)
                    return {"error_detail": "设置剪贴板数据失败", "params": {"method": "ctypes"}}
                owned = False
            finally:
                user32.CloseClipboard()
            return {"text": content}
        except Exception as e:
            if owned:
                kernel32.GlobalFree(h_mem)
            return {"error_detail": str(e), "params": {"method": "ctypes"}}
    except Exception as e:
        return {"error_detail": str(e), "params": {"method": "ctypes"}}


def clipboard_control(action: Literal["read", "write"], content: Optional[str] = None) -> Dict[str, Any]:
    """剪贴板操作 — 小健 2026-06-22 合并read/write"""
    if action == "read":
        t0 = _time_mod.perf_counter()
        result = _read_clipboard()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if "error_detail" in result:
            llm_data = _build_clipboard_control_llm_data("error", duration_ms, "read", detail=result["error_detail"], hint="请检查剪贴板读取权限或确保剪贴板未被其他程序占用")
            return build_error(data={}, llm_data=llm_data)
        text = result.get("text", "")
        original_len = len(text)
        if len(text) > CLIPBOARD_INPUT_MAX_CHARS:
            result["text"] = text[:CLIPBOARD_INPUT_MAX_CHARS] + "\n... (截断: 剪贴板内容超过200KB)"
            result["truncated"] = True
        llm_data = _build_clipboard_control_llm_data("success", duration_ms, "read", original_len)
        # ---- observation_formatter route [read mode] --------------------------------
        # branch: #10 raw text
        # trigger: "text" in data and isinstance(data["text"], str)
        # handler: _format_text_content(data) — 正文+元数据拼接
        # file:    observation_formatter.py:124-126
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)
    elif action == "write":
        if not content:
            llm_data = _build_clipboard_control_llm_data("error", 0, "write", err_code=ERR_DESKTOP_CLIPBOARD, detail="content参数不能为空", hint="请提供要写入的content内容")
            return build_error(data={}, llm_data=llm_data)
        t0 = _time_mod.perf_counter()
        result = _write_clipboard(content)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if "error_detail" in result:
            llm_data = _build_clipboard_control_llm_data("error", duration_ms, "write", content=content, detail=result["error_detail"], hint="请检查剪贴板写入权限或确保剪贴板未被其他程序占用")
            return build_error(data={}, llm_data=llm_data)
        llm_data = _build_clipboard_control_llm_data("success", duration_ms, "write", len(content), content=content)
        # ---- observation_formatter route [write mode] --------------------------------
        # branch: #10 raw text
        # trigger: "text" in data and isinstance(data["text"], str)
        # handler: _format_text_content(data) — 正文+元数据拼接
        # file:    observation_formatter.py:148-149
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)
    else:
        llm_data = _build_clipboard_control_llm_data("error", 0, action, err_code=ERR_DESKTOP_CLIPBOARD, detail=f"无效的action: {action}", hint="请使用read或write作为action参数")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["clipboard_control"]
