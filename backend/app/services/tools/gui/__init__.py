# -*- coding: utf-8 -*-
"""
GUI 模块 - GUI操作工具

【架构规范】2026-05-02 小沈

Author: 小沈 - 2026-05-02
"""

from app.services.tools.gui import gui_register
from app.services.tools.gui import gui_helpers_register
from app.services.tools.gui import gui_tools
from app.services.tools.gui import gui_helpers

from app.services.tools.gui.gui_tools import (
    click, move, scroll,
    type_text, shortcut, key_combo,
    screenshot, snapshot, screen_record,
    list_windows, focus_window, resize_window,
    ocr, read_clipboard, write_clipboard, send_notification,
)

from app.services.tools.gui.gui_helpers import (
    get_mouse_position, check_screen_size,
    check_window_exists, get_window_position,
    check_screen_capture_permission, check_tesseract_available,
    check_notification_permission,
)

__all__ = [
    "click", "move", "scroll",
    "type_text", "shortcut", "key_combo",
    "screenshot", "snapshot", "screen_record",
    "list_windows", "focus_window", "resize_window",
    "ocr", "read_clipboard", "write_clipboard", "send_notification",
    "get_mouse_position", "check_screen_size",
    "check_window_exists", "get_window_position",
    "check_screen_capture_permission", "check_tesseract_available",
    "check_notification_permission",
]
