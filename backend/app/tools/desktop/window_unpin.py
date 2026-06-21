# -*- coding: utf-8 -*-
"""
window_unpin — 取消窗口置顶(薄封装)
【2026-06-22 小欧】从 desktop_tools.py 拆分为独立文件
"""
from typing import Dict, Any
from app.tools.desktop.window_info import set_window_state


def window_unpin(window_title: str) -> Dict[str, Any]:
    """取消窗口置顶 — 小欧 2026-06-22"""
    return set_window_state(window_title, "unpin")


__all__ = ["window_unpin"]
