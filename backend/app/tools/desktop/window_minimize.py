# -*- coding: utf-8 -*-
"""
window_minimize — 最小化窗口(薄封装)
【2026-06-22 小欧】从 desktop_tools.py 拆分为独立文件
"""
from typing import Dict, Any
from app.tools.desktop.window_info import set_window_state


def window_minimize(window_title: str) -> Dict[str, Any]:
    """最小化指定窗口 — 小欧 2026-06-22"""
    return set_window_state(window_title, "minimize")


__all__ = ["window_minimize"]
