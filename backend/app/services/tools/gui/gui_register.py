# -*- coding: utf-8 -*-
"""
GUI Register - GUI操作工具注册点

【架构规范】2026-05-02 小沈
"""

from app.services.tools.gui import gui_tools

__all__ = [
    "click", "move", "scroll",
    "type_text", "shortcut", "key_combo",
    "screenshot", "snapshot", "screen_record",
    "list_windows", "focus_window", "resize_window",
    "ocr",
]
