# -*- coding: utf-8 -*-
"""DESKTOP Tools - 桌面工具模块"""

from app.services.tools.desktop.desktop_register import *
from app.services.tools.desktop.desktop_tools import (
    list_windows,
    get_window_info,
    set_window_state,
)

__all__ = [
    "list_windows",
    "get_window_info",
    "set_window_state",
]