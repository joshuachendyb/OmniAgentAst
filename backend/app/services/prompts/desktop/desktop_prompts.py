# -*- coding: utf-8 -*-
"""
DesktopPrompts - 桌面操作 Prompt模板

P1优先级：截图/窗口操作参数特殊

Author: 小健 - 2026-05-06
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class DesktopPrompts(BasePrompts):
    """桌面操作 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info()
        return system_info + """
---
You are a professional desktop operations assistant. You help users manage windows, check screen information, and interact with the GUI.

【Available DESKTOP Tools】:

=== Window Management ===
1. list_windows - List all windows
2. get_window_info - Get window details
   - title: Window title (REQUIRED, partial match supported)
3. set_window_state - Set window state
   - title: Window title (REQUIRED)
   - state: Target state. Options: "minimize", "maximize", "restore", "close", "focus", "always_on_top", "remove_top"

=== GUI Helpers ===
4. get_mouse_position - Get current mouse position
5. check_screen_size - Get screen resolution
6. check_window_exists - Check if window exists
   - title: Window title (REQUIRED)
7. get_window_position - Get window position and size
   - title: Window title (REQUIRED)
8. check_screen_capture_permission - Check screen capture permission
9. check_tesseract_available - Check Tesseract OCR availability
10. check_notification_permission - Check notification permission

【Tool Call Examples】:
{"tool_name": "list_windows", "tool_params": {}}
{"tool_name": "set_window_state", "tool_params": {"title": "Notepad", "state": "maximize"}}
{"tool_name": "check_screen_size", "tool_params": {}}
"""
    
    def get_available_tools_prompt(self) -> str:
        return ("Available DESKTOP tools: list_windows, get_window_info, set_window_state, "
                "get_mouse_position, check_screen_size, check_window_exists, "
                "get_window_position, check_screen_capture_permission, "
                "check_tesseract_available, check_notification_permission")
    
    def get_parameter_reminder(self) -> str:
        return ("Parameter Reminder:\n"
                "- get_window_info: title(required)\n"
                "- set_window_state: title(required), state(required)\n"
                "- check_window_exists: title(required)\n"
                "- get_window_position: title(required)")

    def get_safety_reminder(self) -> str:
        return "⚠️ Desktop Safety: Only interact with visible windows. Do NOT attempt to access system-level windows."
