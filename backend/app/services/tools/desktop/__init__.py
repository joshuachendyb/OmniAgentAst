# -*- coding: utf-8 -*-
"""DESKTOP Tools - 桌面工具模块（26→10精简方案）- 小沈 2026-05-17"""

from app.services.tools.desktop.desktop_register import *
from app.services.tools.desktop.desktop_tools import (
    window_info,
    window_control,
    mouse_control,
    keyboard_control,
    screen_capture,
    clipboard_control,
)

__all__ = [
    "window_info",
    "window_control",
    "mouse_control",
    "keyboard_control",
    "screen_capture",
    "clipboard_control",
]