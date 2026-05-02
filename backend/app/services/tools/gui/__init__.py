# -*- coding: utf-8 -*-
"""
GUI 模块 - GUI操作工具

【架构规范】2026-05-02 小沈

Author: 小沈 - 2026-05-02
"""

from app.services.tools.gui import gui_register
from app.services.tools.gui import gui_tools

from app.services.tools.gui.gui_tools import (
    click, move, scroll,
    type_text, shortcut, key_combo,
    screenshot, snapshot, screen_record,
    list_windows, focus_window, resize_window,
    ocr,
)

__all__ = [
    "click", "move", "scroll",
    "type_text", "shortcut", "key_combo",
    "screenshot", "snapshot", "screen_record",
    "list_windows", "focus_window", "resize_window",
    "ocr",
]
