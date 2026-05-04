# -*- coding: utf-8 -*-
"""
DESKTOP Tools - 桌面工具实现（窗口管理）

【架构规范】2026-04-29 小沈

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

【工具列表】窗口管理工具
1. list_windows - 列出所有窗口
2. get_window_info - 获取窗口详细信息
3. set_window_state - 设置窗口状态（最大化/最小化/还原/置顶）

创建时间: 2026-04-29
"""

import platform
from typing import Any, Dict, List, Optional
from app.utils.logger import logger

if platform.system() == "Windows":
    import win32gui
    import win32con
    import win32api
    import ctypes
    from ctypes import wintypes


def _get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    """获取窗口位置和大小"""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        return {
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1]
        }
    except:
        return None


def _is_window_visible(hwnd: int) -> bool:
    """检查窗口是否可见"""
    try:
        return win32gui.IsWindowVisible(hwnd)
    except:
        return False


def _get_window_state(hwnd: int) -> str:
    """获取窗口状态"""
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return "minimized"
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMAXIMIZED:
            return "maximized"
        elif placement[1] == win32con.SW_SHOWMINIMIZED:
            return "minimized"
        else:
            return "normal"
    except:
        return "unknown"


def _enum_windows_callback(hwnd: int, windows: List[Dict]) -> bool:
    """枚举窗口回调函数"""
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        
        rect = _get_window_rect(hwnd)
        state = _get_window_state(hwnd)
        
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "state": state,
            "position": rect
        })
    except:
        pass
    return True


def list_windows(
    include_minimized: bool = False,
    filter_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    列出所有窗口

    Args:
        include_minimized: 是否包含最小化的窗口，默认 False
        filter_title: 按窗口标题过滤

    Returns:
        Dict with code, data, message
    """
    try:
        if platform.system() != "Windows":
            return {
                "code": "ERROR",
                "data": None,
                "message": "此功能仅支持 Windows 系统"
            }
        
        windows = []
        win32gui.EnumWindows(_enum_windows_callback, windows)
        
        if not include_minimized:
            windows = [w for w in windows if w["state"] != "minimized"]
        
        if filter_title:
            windows = [w for w in windows if filter_title.lower() in w["title"].lower()]
        
        return {
            "code": "SUCCESS",
            "data": {
                "windows": windows,
                "total": len(windows)
            },
            "message": f"共找到 {len(windows)} 个窗口"
        }
        
    except Exception as e:
        logger.error(f"list_windows error: {e}")
        return {
            "code": "ERROR",
            "data": None,
            "message": f"获取窗口列表失败: {str(e)}"
        }


def get_window_info(window_title: str) -> Dict[str, Any]:
    """
    获取窗口详细信息

    Args:
        window_title: 窗口标题（精确匹配或模糊匹配）

    Returns:
        Dict with code, data, message
    """
    try:
        if platform.system() != "Windows":
            return {
                "code": "ERROR",
                "data": None,
                "message": "此功能仅支持 Windows 系统"
            }
        
        target_hwnd = None
        
        def find_window_callback(hwnd: int, windows: List) -> bool:
            nonlocal target_hwnd
            try:
                title = win32gui.GetWindowText(hwnd)
                if title and window_title.lower() in title.lower():
                    windows.append(hwnd)
            except:
                pass
            return True
        
        windows = []
        win32gui.EnumWindows(find_window_callback, windows)
        
        if not windows:
            return {
                "code": "ERROR",
                "data": None,
                "message": f"未找到窗口: {window_title}"
            }
        
        hwnd = windows[0]
        title = win32gui.GetWindowText(hwnd)
        rect = _get_window_rect(hwnd)
        state = _get_window_state(hwnd)
        
        try:
            class_name = win32gui.GetClassName(hwnd)
        except:
            class_name = "Unknown"
        
        try:
            process_id = win32api.GetWindowThreadProcessId(hwnd)[0]
        except:
            process_id = 0
        
        info = {
            "hwnd": hwnd,
            "title": title,
            "class_name": class_name,
            "state": state,
            "position": rect,
            "process_id": process_id,
            "is_visible": win32gui.IsWindowVisible(hwnd),
            "is_enabled": win32gui.IsWindowEnabled(hwnd),
        }
        
        return {
            "code": "SUCCESS",
            "data": info,
            "message": f"获取窗口信息成功: {title}"
        }
        
    except Exception as e:
        logger.error(f"get_window_info error: {e}")
        return {
            "code": "ERROR",
            "data": None,
            "message": f"获取窗口信息失败: {str(e)}"
        }


def set_window_state(window_title: str, action: str) -> Dict[str, Any]:
    """
    设置窗口状态

    Args:
        window_title: 窗口标题
        action: 操作类型：maximize, minimize, restore, topmost, unpin

    Returns:
        Dict with code, data, message
    """
    try:
        if platform.system() != "Windows":
            return {
                "code": "ERROR",
                "data": None,
                "message": "此功能仅支持 Windows 系统"
            }
        
        valid_actions = ["maximize", "minimize", "restore", "topmost", "unpin"]
        if action not in valid_actions:
            return {
                "code": "ERROR",
                "data": None,
                "message": f"无效的操作: {action}，支持的操作为: {valid_actions}"
            }
        
        def find_window_callback(hwnd: int, windows: List) -> bool:
            try:
                title = win32gui.GetWindowText(hwnd)
                if title and window_title.lower() in title.lower():
                    windows.append(hwnd)
            except:
                pass
            return True
        
        windows = []
        win32gui.EnumWindows(find_window_callback, windows)
        
        if not windows:
            return {
                "code": "ERROR",
                "data": None,
                "message": f"未找到窗口: {window_title}"
            }
        
        hwnd = windows[0]
        title = win32gui.GetWindowText(hwnd)
        
        if action == "maximize":
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            msg = f"已最大化窗口: {title}"
        elif action == "minimize":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            msg = f"已最小化窗口: {title}"
        elif action == "restore":
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            msg = f"已还原窗口: {title}"
        elif action == "topmost":
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            msg = f"已置顶窗口: {title}"
        elif action == "unpin":
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            msg = f"已取消置顶窗口: {title}"
        
        return {
            "code": "SUCCESS",
            "data": {
                "window_title": title,
                "action": action,
                "hwnd": hwnd
            },
            "message": msg
        }
        
    except Exception as e:
        logger.error(f"set_window_state error: {e}")
        return {
            "code": "ERROR",
            "data": None,
            "message": f"设置窗口状态失败: {str(e)}"
        }
