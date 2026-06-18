# -*- coding: utf-8 -*-
"""DESKTOP Tools - 桌面工具模块 — 小欧 2026-06-17"""

from app.tools.desktop.desktop_register import *
from app.tools.desktop.desktop_tools import (
    window_info,
    window_focus,
    window_resize,
    window_maximize,
    window_minimize,
    window_restore,
    window_topmost,
    window_unpin,
    mouse_click,
    mouse_move,
    mouse_scroll,
    mouse_position,
    keyboard_control,
    screen_capture,
    clipboard_read,
    clipboard_write,
)

__all__ = [
    "window_info",
    "window_focus",
    "window_resize",
    "window_maximize",
    "window_minimize",
    "window_restore",
    "window_topmost",
    "window_unpin",
    "mouse_click",
    "mouse_move",
    "mouse_scroll",
    "mouse_position",
    "keyboard_control",
    "screen_capture",
    "clipboard_read",
    "clipboard_write",
]