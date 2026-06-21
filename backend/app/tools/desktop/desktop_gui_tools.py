# -*- coding: utf-8 -*-
"""
GUI操作工具函数模块
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-05-02 小沈
【设计依据】按文档第9章 Tool 92-104 定义

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件:
1. *_tools.py: 函数实现(必须有详细注释)
2. *_schema.py: Pydantic 模型(输入参数定义)
3. *_register.py: 显式注册(description + examples + input_model)

包含12个工具:
- 鼠标: click, move, scroll
- 键盘: type_text, shortcut, key_combo
- 屏幕: screenshot, snapshot, screen_record
- 窗口: list_windows, focus_window, resize_window
- OCR: ocr

Author: 小沈 - 2026-05-02
"""

import importlib
import os
import tempfile
import time as _time_mod
from typing import Dict, Any, List, Optional
from pathlib import Path
from app.utils.time_utils import timestamp_for_filename

from app.tools.tool_response import build_success, build_error
from app.utils.tool_result_formatter import truncate_data_for_frontend, truncate_text
from app.tools.toolhelper.common_helper import _check_module
from app.constants import (
    ERR_DESKTOP_CLIPBOARD,
    ERR_DESKTOP_MOUSE_CLICK,
    ERR_DESKTOP_MOUSE_MOVE,
    ERR_DESKTOP_MOUSE_SCROLL,
    ERR_DESKTOP_NOTIFICATION,
    ERR_FILE_MOVE_FAILED,
    ERR_FOCUS_WINDOW,
    ERR_KEYBOARD_SHORTCUT,
    ERR_KEYBOARD_TYPE,
    ERR_KEY_COMBO,
    ERR_NO_IMAGEIO,
    ERR_NO_NUMPY,
    ERR_NO_PYAUTOGUI,
    ERR_NO_RECORD_LIB,
    ERR_NO_SCREENSHOT_LIB,
    ERR_NO_TESSERACT,
    ERR_NO_WIN10TOAST,
    ERR_NO_WIN32GUI,
    ERR_OCR,
    ERR_SCREENSHOT,
    ERR_SCREEN_RECORD,
    ERR_SCREEN_SNAPSHOT,
    ERR_WINDOW_NOT_FOUND,
    ERR_WINDOW_RESIZE,
)


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


# ========== builder函数 ==========

def _build_click_llm_data(exec_code: str, duration_ms: int, x, y, button: str = "", click_type: str = "",
                           err_code: str = "", detail: str = "") -> dict:
    """mouse_click的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"鼠标点击失败: ({x},{y})",
            "action": {"tool": "mouse_click", "tool_zh": "鼠标点击", "target": f"({x},{y})", "params": {"x": x, "y": y, "button": button}},
            "status": {"exec_code": "error", "message": "点击失败", "code": err_code or ERR_DESKTOP_MOUSE_CLICK, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"点击完成: ({x}, {y}) {button} {click_type}",
        "action": {"tool": "mouse_click", "tool_zh": "鼠标点击", "target": f"({x},{y})", "params": {"x": x, "y": y, "button": button, "click_type": click_type}},
        "status": {"exec_code": "success", "message": "点击完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_move_llm_data(exec_code: str, duration_ms: int, x: int, y: int,
                          err_code: str = "", detail: str = "") -> dict:
    """mouse_move的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"鼠标移动失败: ({x},{y})",
            "action": {"tool": "mouse_move", "tool_zh": "鼠标移动", "target": f"({x},{y})", "params": {"x": x, "y": y}},
            "status": {"exec_code": "error", "message": "鼠标移动失败", "code": err_code or ERR_DESKTOP_MOUSE_MOVE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"鼠标移动到: ({x}, {y})",
        "action": {"tool": "mouse_move", "tool_zh": "鼠标移动", "target": f"({x},{y})", "params": {"x": x, "y": y}},
        "status": {"exec_code": "success", "message": "鼠标移动完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_scroll_llm_data(exec_code: str, duration_ms: int, direction: str = "", amount: int = 0,
                            err_code: str = "", detail: str = "") -> dict:
    """mouse_scroll的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "鼠标滚动失败",
            "action": {"tool": "mouse_scroll", "tool_zh": "鼠标滚动", "target": "", "params": {"direction": direction, "amount": amount}},
            "status": {"exec_code": "error", "message": "滚动失败", "code": err_code or ERR_DESKTOP_MOUSE_SCROLL, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"滚动完成: {direction} {amount}单位",
        "action": {"tool": "mouse_scroll", "tool_zh": "鼠标滚动", "target": "", "params": {"direction": direction, "amount": amount}},
        "status": {"exec_code": "success", "message": "滚动完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_type_text_llm_data(exec_code: str, duration_ms: int, text_len: int = 0,
                               err_code: str = "", detail: str = "") -> dict:
    """keyboard_type的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "键盘输入失败",
            "action": {"tool": "keyboard_type", "tool_zh": "键盘输入", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "输入文本失败", "code": err_code or ERR_KEYBOARD_TYPE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"输入文本完成: {text_len}个字符",
        "action": {"tool": "keyboard_type", "tool_zh": "键盘输入", "target": "", "params": {"text_length": text_len}},
        "status": {"exec_code": "success", "message": "输入文本完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {"chars": {"value": text_len, "text": f"{text_len}个"}},
    }


def _build_shortcut_llm_data(exec_code: str, duration_ms: int, keys: str = "",
                              err_code: str = "", detail: str = "") -> dict:
    """keyboard_shortcut的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"快捷键执行失败: {keys}",
            "action": {"tool": "keyboard_shortcut", "tool_zh": "快捷键", "target": keys, "params": {}},
            "status": {"exec_code": "error", "message": "快捷键执行失败", "code": err_code or ERR_KEYBOARD_SHORTCUT, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"快捷键执行完成: {keys}",
        "action": {"tool": "keyboard_shortcut", "tool_zh": "快捷键", "target": keys, "params": {"keys": keys}},
        "status": {"exec_code": "success", "message": "快捷键执行完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_key_combo_llm_data(exec_code: str, duration_ms: int, keys=None, action: str = "",
                               err_code: str = "", detail: str = "") -> dict:
    """keyboard_combo的llm_data构建函数 — 小健 2026-06-21"""
    keys_str = str(keys) if keys else ""
    if exec_code == "error":
        return {
            "summary": f"按键操作失败: {keys_str}",
            "action": {"tool": "keyboard_combo", "tool_zh": "按键组合", "target": keys_str, "params": {}},
            "status": {"exec_code": "error", "message": "按键操作失败", "code": err_code or ERR_KEY_COMBO, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"按键操作完成: {keys_str} {action}",
        "action": {"tool": "keyboard_combo", "tool_zh": "按键组合", "target": keys_str, "params": {"keys": keys, "action": action}},
        "status": {"exec_code": "success", "message": "按键操作完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_screenshot_llm_data(exec_code: str, duration_ms: int, output_path: str = "", region=None,
                                err_code: str = "", detail: str = "") -> dict:
    """screen_capture的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "截图失败",
            "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "截图失败", "code": err_code or ERR_SCREENSHOT, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"截图保存到: {output_path}",
        "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": output_path, "params": {"region": region}},
        "status": {"exec_code": "success", "message": "截图完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_snapshot_llm_data(exec_code: str, duration_ms: int, display: int = 1, output_path: str = "",
                              monitor_count: int = 0, err_code: str = "", detail: str = "") -> dict:
    """screen_snapshot的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "快照失败",
            "action": {"tool": "screen_snapshot", "tool_zh": "屏幕快照", "target": "", "params": {"display": display}},
            "status": {"exec_code": "error", "message": "快照失败", "code": err_code or ERR_SCREEN_SNAPSHOT, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    metrics = {}
    if monitor_count > 0:
        metrics["monitors"] = {"value": monitor_count, "text": f"{monitor_count}个"}
    return {
        "summary": f"快照保存到: {output_path}",
        "action": {"tool": "screen_snapshot", "tool_zh": "屏幕快照", "target": f"显示器{display}", "params": {"display": display}},
        "status": {"exec_code": "success", "message": "快照完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def _build_screen_record_llm_data(exec_code: str, duration_ms: int, output_path: str = "",
                                   rec_duration: int = 0, fps: int = 0,
                                   err_code: str = "", detail: str = "") -> dict:
    """screen_record的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "屏幕录制失败",
            "action": {"tool": "screen_record", "tool_zh": "屏幕录制", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "录制失败", "code": err_code or ERR_SCREEN_RECORD, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"屏幕录制完成,已保存到{output_path}",
        "action": {"tool": "screen_record", "tool_zh": "屏幕录制", "target": output_path, "params": {"duration": rec_duration, "fps": fps}},
        "status": {"exec_code": "success", "message": "录制完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"duration": {"value": rec_duration, "text": f"{rec_duration}秒"}, "fps": {"value": fps, "text": f"{fps}fps"}},
    }


def _build_focus_window_llm_data(exec_code: str, duration_ms: int, title: str = "",
                                  err_code: str = "", detail: str = "") -> dict:
    """window_focus的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"聚焦窗口失败: {title}",
            "action": {"tool": "window_focus", "tool_zh": "窗口聚焦", "target": title, "params": {}},
            "status": {"exec_code": "error", "message": "聚焦窗口失败", "code": err_code or ERR_FOCUS_WINDOW, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"窗口已聚焦: {title}",
        "action": {"tool": "window_focus", "tool_zh": "窗口聚焦", "target": title, "params": {}},
        "status": {"exec_code": "success", "message": "窗口聚焦完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_resize_window_llm_data(exec_code: str, duration_ms: int, title: str = "", width: int = 0, height: int = 0,
                                   err_code: str = "", detail: str = "") -> dict:
    """window_resize的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"调整窗口大小失败: {title}",
            "action": {"tool": "window_resize", "tool_zh": "窗口调整", "target": title, "params": {}},
            "status": {"exec_code": "error", "message": "调整窗口大小失败", "code": err_code or ERR_WINDOW_RESIZE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"窗口大小调整完成: {width}x{height}",
        "action": {"tool": "window_resize", "tool_zh": "窗口调整", "target": title, "params": {"width": width, "height": height}},
        "status": {"exec_code": "success", "message": "窗口大小调整完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_ocr_llm_data(exec_code: str, duration_ms: int, image_path: str = "", language: str = "",
                         char_count: int = 0, err_code: str = "", detail: str = "") -> dict:
    """ocr的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "OCR识别失败",
            "action": {"tool": "ocr", "tool_zh": "OCR识别", "target": image_path, "params": {}},
            "status": {"exec_code": "error", "message": "OCR识别失败", "code": err_code or ERR_OCR, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"OCR识别完成: {char_count}个字符",
        "action": {"tool": "ocr", "tool_zh": "OCR识别", "target": image_path, "params": {"language": language}},
        "status": {"exec_code": "success", "message": "OCR识别完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {"chars": {"value": char_count, "text": f"{char_count}个"}},
    }


def _build_clipboard_read_llm_data(exec_code: str, duration_ms: int, char_count: int = 0,
                                    err_code: str = "", detail: str = "") -> dict:
    """clipboard_read的llm_data构建函数 — 小健 2026-06-21"""
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


def _build_clipboard_write_llm_data(exec_code: str, duration_ms: int, char_count: int = 0,
                                     err_code: str = "", detail: str = "") -> dict:
    """clipboard_write的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "剪贴板写入失败",
            "action": {"tool": "clipboard_write", "tool_zh": "剪贴板写入", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "剪贴板写入失败", "code": err_code or ERR_DESKTOP_CLIPBOARD, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"剪贴板写入成功: {char_count}个字符",
        "action": {"tool": "clipboard_write", "tool_zh": "剪贴板写入", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "剪贴板写入成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {"chars": {"value": char_count, "text": f"{char_count}个"}},
    }


def _build_notification_llm_data(exec_code: str, duration_ms: int, title: str = "", notif_duration: int = 0,
                                  err_code: str = "", detail: str = "") -> dict:
    """send_notification的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"通知发送失败: {title}",
            "action": {"tool": "send_notification", "tool_zh": "系统通知", "target": title, "params": {}},
            "status": {"exec_code": "error", "message": "通知发送失败", "code": err_code or ERR_DESKTOP_NOTIFICATION, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"通知已发送: {title}",
        "action": {"tool": "send_notification", "tool_zh": "系统通知", "target": title, "params": {"duration": notif_duration}},
        "status": {"exec_code": "success", "message": "通知发送成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


# ========== 鼠标操作 ==========

def _click(
    x: int = None,
    y: int = None,
    button: str = "left",
    click_type: str = "single"
) -> Dict[str, Any]:
    """模拟鼠标点击 — 小健 2026-06-21 builder改造"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_click_llm_data("error", 0, x, y, button, click_type, ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        clicks = 2 if click_type == "double" else 1
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"x": x, "y": y, "button": button, "click_type": click_type}
        llm_data = _build_click_llm_data("success", duration_ms, x, y, button, click_type)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_click_llm_data("error", duration_ms, x, y, button, click_type, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _move(x: int, y: int, duration: float = 0) -> Dict[str, Any]:
    """移动鼠标到指定位置 — 小健 2026-06-21 builder改造"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_move_llm_data("error", 0, x, y, ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"x": x, "y": y}
        llm_data = _build_move_llm_data("success", duration_ms, x, y)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_llm_data("error", duration_ms, x, y, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _scroll(direction: str, amount: int = 3) -> Dict[str, Any]:
    """模拟鼠标滚轮滚动 — 小健 2026-06-21 builder改造"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_scroll_llm_data("error", 0, direction, amount, ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        scroll_amount = -amount if direction == "down" else amount
        pyautogui.scroll(scroll_amount)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"direction": direction, "amount": amount}
        llm_data = _build_scroll_llm_data("success", duration_ms, direction, amount)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_scroll_llm_data("error", duration_ms, direction, amount, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== 键盘操作 ==========

def _type_text(text: str, interval: float = 0) -> Dict[str, Any]:
    """模拟键盘输入文本 — 小健 2026-06-21 builder改造"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_type_text_llm_data("error", 0, len(text), ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            pyautogui.write(text)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"text_length": len(text)}
        llm_data = _build_type_text_llm_data("success", duration_ms, len(text))
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_type_text_llm_data("error", duration_ms, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _shortcut(keys: str) -> Dict[str, Any]:
    """执行键盘快捷键组合 — 小健 2026-06-21 builder改造"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_shortcut_llm_data("error", 0, keys, ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        key_list = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"keys": keys}
        llm_data = _build_shortcut_llm_data("success", duration_ms, keys)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shortcut_llm_data("error", duration_ms, keys, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _key_combo(keys: List[str], action: str = "press") -> Dict[str, Any]:
    """按住多个键后释放 — 小健 2026-06-21 builder改造"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_key_combo_llm_data("error", 0, keys, action, ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        if action == "press":
            pyautogui.hotkey(*keys)
        elif action == "hold":
            for key in keys:
                pyautogui.keyDown(key)
        elif action == "release":
            for key in keys:
                pyautogui.keyUp(key)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"keys": keys, "action": action}
        llm_data = _build_key_combo_llm_data("success", duration_ms, keys, action)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_key_combo_llm_data("error", duration_ms, keys, action, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== 屏幕操作 ==========

def _screenshot(output_path: str = None, region: Dict[str, int] = None) -> Dict[str, Any]:
    """截取屏幕截图 — 小健 2026-06-21 builder改造"""
    try:
        import pyautogui
    except ImportError:
        return build_error(data={"error_detail": "pyautogui库未安装"}, llm_data=_build_screenshot_llm_data("error", 0, err_code=ERR_NO_PYAUTOGUI))
    t0 = _time_mod.perf_counter()
    try:
        if output_path is None:
            timestamp = timestamp_for_filename()
            output_path = os.path.join(tempfile.gettempdir(), f"screenshot_{timestamp}.png")

        if region:
            r = (region.get("x", 0), region.get("y", 0), region.get("width", 800), region.get("height", 600))
            img = pyautogui.screenshot(region=r)
        else:
            img = pyautogui.screenshot()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"image_path": output_path}
        llm_data = _build_screenshot_llm_data("success", duration_ms, output_path, region)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_screenshot_llm_data("error", duration_ms, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _snapshot(display: int = 1) -> Dict[str, Any]:
    """获取完整桌面状态快照 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        import mss
    except ImportError:
        try:
            import pyautogui
            timestamp = timestamp_for_filename()
            output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
            img = pyautogui.screenshot()
            img.save(output_path)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"image_path": output_path, "display": display}
            llm_data = _build_snapshot_llm_data("success", duration_ms, display, output_path)
            return build_success(data=data, llm_data=llm_data)
        except ImportError:
            return build_error(data={"error_detail": "需要安装 mss 或 pyautogui 库"}, llm_data=_build_snapshot_llm_data("error", 0, display, err_code=ERR_NO_SCREENSHOT_LIB))
    try:
        timestamp = timestamp_for_filename()
        output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
        with mss.mss() as sct:
            monitors = sct.monitors
            if display < 1 or display >= len(monitors):
                mon_index = 1
            else:
                mon_index = display
            img = sct.grab(monitors[mon_index])
            from PIL import Image
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(output_path)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"image_path": output_path, "display": display, "monitors": len(monitors) - 1}
        llm_data = _build_snapshot_llm_data("success", duration_ms, display, output_path, len(monitors) - 1)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_snapshot_llm_data("error", duration_ms, display, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def screen_record(duration: int, output_path: Optional[str] = None, fps: int = 15) -> Dict[str, Any]:
    """录制屏幕视频 — 小健 2026-06-21 builder改造"""
    try:
        import mss
        from PIL import Image
    except ImportError:
        return build_error(data={"error_detail": "需要安装 mss 和 PIL 库"}, llm_data=_build_screen_record_llm_data("error", 0, err_code=ERR_NO_RECORD_LIB))
    try:
        import numpy
    except ImportError:
        return build_error(data={"error_detail": "需要安装 numpy 库"}, llm_data=_build_screen_record_llm_data("error", 0, err_code=ERR_NO_NUMPY))
    try:
        import imageio.v2 as imageio
    except ImportError:
        try:
            import imageio
        except ImportError:
            return build_error(data={"error_detail": "需要安装 imageio 库"}, llm_data=_build_screen_record_llm_data("error", 0, err_code=ERR_NO_IMAGEIO))
    t0 = _time_mod.perf_counter()
    try:
        if output_path is None:
            timestamp = timestamp_for_filename()
            output_path = os.path.join(tempfile.gettempdir(), f"screen_record_{timestamp}.mp4")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            frames = []
            start_time = _time_mod.time()
            interval = 1.0 / fps

            while _time_mod.time() - start_time < duration:
                img = sct.grab(monitor)
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                frames.append(numpy.array(pil_img))
                _time_mod.sleep(interval)

            imageio.mimwrite(output_path, frames, fps=fps)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"output_path": output_path, "duration": duration, "fps": fps}
        llm_data = _build_screen_record_llm_data("success", duration_ms, output_path, duration, fps)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_screen_record_llm_data("error", duration_ms, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== 窗口操作 ==========

def _focus_window(title: str) -> Dict[str, Any]:
    """聚焦指定窗口 — 小健 2026-06-21 builder改造"""
    try:
        import win32gui
    except ImportError:
        return build_error(data={"error_detail": "需要安装 pywin32 库"}, llm_data=_build_focus_window_llm_data("error", 0, title, ERR_NO_WIN32GUI))
    t0 = _time_mod.perf_counter()
    try:
        target_hwnd = None
        def _enum_cb(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                win_title = win32gui.GetWindowText(hwnd)
                if title.lower() in win_title.lower():
                    target_hwnd = hwnd
            return True
        win32gui.EnumWindows(_enum_cb, None)

        if target_hwnd:
            win32gui.SetForegroundWindow(target_hwnd)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"title": title, "hwnd": target_hwnd}
            llm_data = _build_focus_window_llm_data("success", duration_ms, title)
            return build_success(data=data, llm_data=llm_data)
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_focus_window_llm_data("error", duration_ms, title, ERR_WINDOW_NOT_FOUND)
            return build_error(data={"error_detail": f"未找到窗口: {title}", "window_title": title}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_focus_window_llm_data("error", duration_ms, title, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _resize_window(title: str, width: int = None, height: int = None) -> Dict[str, Any]:
    """调整窗口大小 — 小健 2026-06-21 builder改造"""
    try:
        import win32gui
    except ImportError:
        return build_error(data={"error_detail": "需要安装 pywin32 库"}, llm_data=_build_resize_window_llm_data("error", 0, title, err_code=ERR_NO_WIN32GUI))
    t0 = _time_mod.perf_counter()
    try:
        target_hwnd = None
        def _enum_cb(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                win_title = win32gui.GetWindowText(hwnd)
                if title.lower() in win_title.lower():
                    target_hwnd = hwnd
            return True
        win32gui.EnumWindows(_enum_cb, None)

        if not target_hwnd:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_resize_window_llm_data("error", duration_ms, title, err_code=ERR_WINDOW_NOT_FOUND)
            return build_error(data={"error_detail": f"未找到窗口: {title}", "window_title": title}, llm_data=llm_data)

        left, top, right, bottom = win32gui.GetWindowRect(target_hwnd)
        curr_width = right - left
        curr_height = bottom - top

        new_width = width if width else curr_width
        new_height = height if height else curr_height

        win32gui.MoveWindow(target_hwnd, left, top, new_width, new_height, True)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"title": title, "width": new_width, "height": new_height}
        llm_data = _build_resize_window_llm_data("success", duration_ms, title, new_width, new_height)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_resize_window_llm_data("error", duration_ms, title, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== OCR操作 ==========

def ocr(image_path: str, language: str = "eng") -> Dict[str, Any]:
    """从图片中识别文字 — 小健 2026-06-21 builder改造"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return build_error(data={"error_detail": "需要安装 pytesseract 和 PIL 库"}, llm_data=_build_ocr_llm_data("error", 0, image_path, language, err_code=ERR_NO_TESSERACT))
    t0 = _time_mod.perf_counter()
    try:
        path = Path(image_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_ocr_llm_data("error", duration_ms, image_path, language, err_code=ERR_OCR)
            return build_error(data={"error_detail": f"图片文件不存在: {image_path}", "file_path": image_path}, llm_data=llm_data)

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=language)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = truncate_data_for_frontend({"text": text, "language": language, "char_count": len(text)})
        llm_data = _build_ocr_llm_data("success", duration_ms, image_path, language, len(text))
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_ocr_llm_data("error", duration_ms, image_path, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== 剪贴板操作 ==========

def _read_clipboard() -> Dict[str, Any]:
    """读取剪贴板内容 — 小健 2026-06-21 builder改造"""
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
            kernel32 = ctypes.windll.kernel32
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
            return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _write_clipboard(content: str) -> Dict[str, Any]:
    """写入内容到剪贴板 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        import pyperclip
        pyperclip.copy(content)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = truncate_data_for_frontend({"content": content})
        llm_data = _build_clipboard_write_llm_data("success", duration_ms, len(content))
        return build_success(data=data, llm_data=llm_data)
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
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_clipboard_write_llm_data("error", duration_ms, err_code=ERR_DESKTOP_CLIPBOARD, detail="内存分配失败")
                return build_error(data={"error_detail": "内存分配失败"}, llm_data=llm_data)
            p_mem = kernel32.GlobalLock(h_mem)
            if p_mem:
                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)
                user32.OpenClipboard(None)
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_TEXT, h_mem)
                user32.CloseClipboard()
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                data = {"content": content}
                llm_data = _build_clipboard_write_llm_data("success", duration_ms, len(content))
                return build_success(data=data, llm_data=llm_data)
            else:
                kernel32.GlobalFree(h_mem)
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_clipboard_write_llm_data("error", duration_ms, err_code=ERR_DESKTOP_CLIPBOARD, detail="内存锁定失败")
                return build_error(data={"error_detail": "内存锁定失败"}, llm_data=llm_data)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_clipboard_write_llm_data("error", duration_ms, detail=str(e))
            return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== 通知操作 ==========

def send_notification(title: str, message: str, duration: int = 5) -> Dict[str, Any]:
    """发送系统通知 — 小健 2026-06-21 builder改造"""
    if not _check_module("win10toast"):
        return build_error(data={"error_detail": "win10toast库未安装"}, llm_data=_build_notification_llm_data("error", 0, title, err_code=ERR_NO_WIN10TOAST))

    from win10toast import ToastNotifier
    t0 = _time_mod.perf_counter()
    try:
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"title": title, "message": message, "duration": duration}
        llm_data = _build_notification_llm_data("success", duration_ms, title, duration)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_notification_llm_data("error", duration_ms, title, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
