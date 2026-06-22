# -*- coding: utf-8 -*-
"""
keyboard_control — 键盘控制
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import importlib
import time as _time_mod
from typing import Dict, Any, List, Literal

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_INVALID_ACTION, ERR_KEYBOARD_TYPE, ERR_KEYBOARD_SHORTCUT, ERR_KEY_COMBO


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


def _build_keyboard_control_llm_data(exec_code: str, duration_ms: int, action: str, text_or_keys: str,
                                      err_code: str = "", detail: str = "") -> dict:
    """keyboard_control的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"无效的键盘操作: {action}",
            "action": {"tool": "keyboard_control", "tool_zh": "键盘控制", "target": action, "params": {"action": action}},
            "status": {"exec_code": "error", "message": f"无效的键盘操作: {action}", "code": err_code or ERR_INVALID_ACTION, "detail": detail, "hint": "请使用支持的操作类型"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"键盘操作完成: {action}",
        "action": {"tool": "keyboard_control", "tool_zh": "键盘控制", "target": action, "params": {"action": action}},
        "status": {"exec_code": "success", "message": "键盘操作完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _type_text(text: str, interval: float = 0) -> Dict[str, Any]:
    """模拟键盘输入文本(内聚) — 小健 2026-06-22"""
    if not _check_pyautogui():
        return {"error_detail": "pyautogui库未安装", "params": {"library": "pyautogui"}}
    try:
        import pyautogui
        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            pyautogui.write(text)
        return {"text_length": len(text)}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def _shortcut(keys: str) -> Dict[str, Any]:
    """执行键盘快捷键组合(内聚) — 小健 2026-06-22"""
    if not _check_pyautogui():
        return {"error_detail": "pyautogui库未安装", "params": {"library": "pyautogui"}}
    try:
        import pyautogui
        key_list = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        return {"keys": keys}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def _key_combo(keys: List[str], action: str = "press") -> Dict[str, Any]:
    """按住多个键后释放(内聚) — 小健 2026-06-22"""
    if not _check_pyautogui():
        return {"error_detail": "pyautogui库未安装", "params": {"library": "pyautogui"}}
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
        return {"keys": keys, "action": action}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def keyboard_control(action: Literal["type", "shortcut", "combo"], text_or_keys: str, interval: float = 0) -> Dict[str, Any]:
    """统一键盘控制入口 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    
    if action == "type":
        result = _type_text(text=text_or_keys, interval=interval)
    elif action == "shortcut":
        result = _shortcut(keys=text_or_keys)
    elif action == "combo":
        key_list = [k.strip() for k in text_or_keys.split(",")]
        result = _key_combo(keys=key_list)
    else:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_keyboard_control_llm_data("error", duration_ms, action, text_or_keys)
        return build_error(data={"error_detail": f"无效的键盘操作: {action}", "params": {"action": action}}, llm_data=llm_data)
    
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if "error_detail" in result:
        err_code = {
            "type": ERR_KEYBOARD_TYPE,
            "shortcut": ERR_KEYBOARD_SHORTCUT,
            "combo": ERR_KEY_COMBO,
        }.get(action, ERR_INVALID_ACTION)
        llm_data = _build_keyboard_control_llm_data("error", duration_ms, action, text_or_keys, err_code=err_code, detail=result["error_detail"])
        return build_error(data=result, llm_data=llm_data)
    
    llm_data = _build_keyboard_control_llm_data("success", duration_ms, action, text_or_keys)
    return build_success(data=result, llm_data=llm_data)


__all__ = ["keyboard_control"]