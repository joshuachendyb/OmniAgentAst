# -*- coding: utf-8 -*-
"""
window_maximize — 最大化窗口(薄封装)
【2026-06-22 小欧】从 desktop_tools.py 拆分为独立文件
"""
from typing import Dict, Any
from app.tools.desktop.window_info import set_window_state


def window_maximize(window_title: str) -> Dict[str, Any]:
    """最大化指定窗口 — 小欧 2026-06-22"""
    return set_window_state(window_title, "maximize")


__all__ = ["window_maximize"]
