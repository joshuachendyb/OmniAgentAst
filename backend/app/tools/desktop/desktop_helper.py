# -*- coding: utf-8 -*-
"""
desktop工具层公共函数 — 小健 2026-06-27
"""
import importlib


def check_pyautogui_available() -> bool:
    """检查pyautogui库是否可用 — 小健 2026-06-27"""
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False