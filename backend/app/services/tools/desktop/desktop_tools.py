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
【修正 2026-05-05 小沈】小健检查发现的问题：
1. pywin32未安装/非Windows时模块加载崩溃 → 改为try/except惰性导入 + HAS_WIN32标志
2. 裸except(7处) → 改为 except Exception
3. 错误码"ERROR" → 统一为 ERR_XXX
4. 多窗口匹配只取第一个 → 加 matched_count 提示
5. action缺少枚举约束 → Schema改Literal（在schema.py中）
6. 删除死代码 target_hwnd / _is_window_visible
7. 重复定义 find_window_callback → 抽取 _find_windows_by_title 公共函数
"""

import platform
from typing import Any, Dict, List, Optional, Literal
from app.utils.logger import logger
from app.services.tools.tool_result_utils import build_next_actions  # 小沈 2026-05-19

_HAS_WIN32 = False
_win32gui = None
_win32con = None
_win32api = None

if platform.system() == "Windows":
    try:
        import win32gui as _win32gui_mod
        import win32con as _win32con_mod
        import win32api as _win32api_mod
        _win32gui = _win32gui_mod
        _win32con = _win32con_mod
        _win32api = _win32api_mod
        _HAS_WIN32 = True
    except ImportError:
        _HAS_WIN32 = False
        logger.warning("pywin32未安装，桌面工具将不可用。请执行: pip install pywin32")


def _check_platform() -> Optional[Dict[str, Any]]:
    """检查平台和依赖是否可用 - 小沈 2026-05-05"""
    if platform.system() != "Windows":
        return {
            "code": "ERR_NOT_WINDOWS",
            "data": None,
            "message": "此功能仅支持 Windows 系统"
        }
    if not _HAS_WIN32:
        return {
            "code": "ERR_NO_PYWIN32",
            "data": None,
            "message": "pywin32库未安装，请先执行: pip install pywin32"
        }
    return None


def _get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    """获取窗口位置和大小 - 小沈 2026-05-05修正"""
    try:
        rect = _win32gui.GetWindowRect(hwnd)
        return {
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1]
        }
    except Exception:
        return None


def _get_window_state(hwnd: int) -> str:
    """获取窗口状态 - 小沈 2026-05-05修正"""
    try:
        if not _win32gui.IsWindowVisible(hwnd):
            return "minimized"
        placement = _win32gui.GetWindowPlacement(hwnd)
        if placement[1] == _win32con.SW_SHOWMAXIMIZED:
            return "maximized"
        elif placement[1] == _win32con.SW_SHOWMINIMIZED:
            return "minimized"
        else:
            return "normal"
    except Exception:
        return "unknown"


def _enum_windows_callback(hwnd: int, windows: List[Dict]) -> bool:
    """枚举窗口回调函数 - 小沈 2026-05-05修正"""
    try:
        if not _win32gui.IsWindowVisible(hwnd):
            return True

        title = _win32gui.GetWindowText(hwnd)
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
    except Exception:
        pass
    return True


def _find_windows_by_title(window_title: str) -> List[int]:
    """按标题模糊匹配查找窗口句柄列表 - 小沈 2026-05-05"""
    windows = []

    def callback(hwnd: int, _: List) -> bool:
        try:
            title = _win32gui.GetWindowText(hwnd)
            if title and window_title.lower() in title.lower():
                windows.append(hwnd)
        except Exception:
            pass
        return True

    _win32gui.EnumWindows(callback, [])
    return windows


def list_windows(
    include_minimized: bool = False,
    filter_title: Optional[str] = None
) -> Dict[str, Any]:
    """列出所有窗口 - 小沈 2026-04-29, 修正 2026-05-05"""
    err = _check_platform()
    if err:
        return err

    try:
        windows = []
        _win32gui.EnumWindows(_enum_windows_callback, windows)

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
            "message": f"共找到 {len(windows)} 个窗口",
            "capabilities_used": ["win32gui"],
            "next_actions": build_next_actions([("get_window_info", "获取窗口详情", "需要查看特定窗口信息时"), ("window_control", "控制窗口", "需要操作窗口时")])
        }

    except Exception as e:
        logger.error(f"list_windows error: {e}")
        return {
            "code": "ERR_LIST_WINDOWS",
            "data": None,
            "message": f"获取窗口列表失败: {str(e)}"
        }


def get_window_info(window_title: str) -> Dict[str, Any]:
    """获取窗口详细信息 - 小沈 2026-04-29, 修正 2026-05-05"""
    err = _check_platform()
    if err:
        return err

    try:
        matched_hwnds = _find_windows_by_title(window_title)

        if not matched_hwnds:
            return {
                "code": "ERR_WINDOW_NOT_FOUND",
                "data": None,
                "message": f"未找到窗口: {window_title}"
            }

        hwnd = matched_hwnds[0]
        title = _win32gui.GetWindowText(hwnd)
        rect = _get_window_rect(hwnd)
        state = _get_window_state(hwnd)

        try:
            class_name = _win32gui.GetClassName(hwnd)
        except Exception:
            class_name = "Unknown"

        try:
            process_id = _win32api.GetWindowThreadProcessId(hwnd)[0]
        except Exception:
            process_id = 0

        info = {
            "hwnd": hwnd,
            "title": title,
            "class_name": class_name,
            "state": state,
            "position": rect,
            "process_id": process_id,
            "is_visible": _win32gui.IsWindowVisible(hwnd),
            "is_enabled": _win32gui.IsWindowEnabled(hwnd),
            "matched_count": len(matched_hwnds),
        }

        msg = f"获取窗口信息成功: {title}"
        if len(matched_hwnds) > 1:
            msg += f"（共匹配到 {len(matched_hwnds)} 个窗口，返回第一个）"

        return {
            "code": "SUCCESS",
            "data": info,
            "message": msg,
            "capabilities_used": ["win32gui"],
            "next_actions": build_next_actions([("window_control", "控制该窗口", "需要操作窗口时")])
        }

    except Exception as e:
        logger.error(f"get_window_info error: {e}")
        return {
            "code": "ERR_GET_WINDOW_INFO",
            "data": None,
            "message": f"获取窗口信息失败: {str(e)}"
        }


def set_window_state(window_title: str, action: str) -> Dict[str, Any]:
    """设置窗口状态 - 小沈 2026-04-29, 修正 2026-05-05

    【2026-05-17 小沈】保留旧实现，供 window_control 内部调用
    """
    err = _check_platform()
    if err:
        return err

    try:
        valid_actions = ["maximize", "minimize", "restore", "topmost", "unpin"]
        if action not in valid_actions:
            return {
                "code": "ERR_INVALID_ACTION",
                "data": None,
                "message": f"无效的操作: {action}，支持的操作为: {valid_actions}"
            }

        matched_hwnds = _find_windows_by_title(window_title)

        if not matched_hwnds:
            return {
                "code": "ERR_WINDOW_NOT_FOUND",
                "data": None,
                "message": f"未找到窗口: {window_title}"
            }

        hwnd = matched_hwnds[0]
        title = _win32gui.GetWindowText(hwnd)

        if action == "maximize":
            _win32gui.ShowWindow(hwnd, _win32con.SW_MAXIMIZE)
            msg = f"已最大化窗口: {title}"
        elif action == "minimize":
            _win32gui.ShowWindow(hwnd, _win32con.SW_MINIMIZE)
            msg = f"已最小化窗口: {title}"
        elif action == "restore":
            _win32gui.ShowWindow(hwnd, _win32con.SW_RESTORE)
            msg = f"已还原窗口: {title}"
        elif action == "topmost":
            _win32gui.SetWindowPos(hwnd, _win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                   _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE)
            msg = f"已置顶窗口: {title}"
        elif action == "unpin":
            _win32gui.SetWindowPos(hwnd, _win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                   _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE)
            msg = f"已取消置顶窗口: {title}"

        if len(matched_hwnds) > 1:
            msg += f"（共匹配到 {len(matched_hwnds)} 个窗口，操作了第一个）"

        return {
            "code": "SUCCESS",
            "data": {
                "window_title": title,
                "action": action,
                "hwnd": hwnd,
                "matched_count": len(matched_hwnds),
            },
            "message": msg,
            "next_actions": build_next_actions([("get_window_info", "确认窗口状态", "需要验证操作结果时")])
        }

    except Exception as e:
        logger.error(f"set_window_state error: {e}")
        return {
            "code": "ERR_SET_WINDOW_STATE",
            "data": None,
            "message": f"设置窗口状态失败: {str(e)}"
        }


# ========== 统一入口函数（26→10精简方案） ==========

def window_control(
    window_title: str,
    action: Literal["focus", "resize", "maximize", "minimize", "restore", "topmost", "unpin"],
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    """统一窗口控制入口 - 小沈 2026-05-17

    合并 set_window_state + focus_window + resize_window
    action: "focus"|"resize"|"maximize"|"minimize"|"restore"|"topmost"|"unpin"
    """
    if action == "focus":
        from app.services.tools.desktop.gui_tools import _focus_window
        result = _focus_window(window_title)
    elif action == "resize":
        from app.services.tools.desktop.gui_tools import _resize_window
        result = _resize_window(window_title, width=width, height=height)
    else:
        result = set_window_state(window_title, action)

    if result.get("code") == "SUCCESS" and "next_actions" not in result:
        result["next_actions"] = build_next_actions([("get_window_info", "确认窗口状态", "需要验证操作结果时")])
    if result.get("code") == "SUCCESS":
        result["capabilities_used"] = ["win32gui", "pyautogui"]
    return result


def mouse_control(
    action: Literal["click", "move", "scroll", "position"],
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: Literal["left", "right", "middle"] = "left",
    direction: Literal["up", "down"] = "down",
    amount: int = 3,
) -> Dict[str, Any]:
    """统一鼠标控制入口 - 小沈 2026-05-17

    合并 click + move + scroll
    action: "click"|"move"|"scroll"|"position"
    """
    # 已从Schema移除的参数，用局部变量保留默认值
    click_type: Literal["single", "double"] = "single"
    duration: float = 0
    if action == "click":
        from app.services.tools.desktop.gui_tools import _click
        result = _click(x=x, y=y, button=button, click_type=click_type)
    elif action == "move":
        from app.services.tools.desktop.gui_tools import _move
        result = _move(x=x, y=y, duration=duration)
    elif action == "scroll":
        from app.services.tools.desktop.gui_tools import _scroll
        result = _scroll(direction=direction, amount=amount)
    elif action == "position":
        from app.services.tools.toolhelper.gui_helper import _get_mouse_position
        result = _get_mouse_position()
    else:
        return {"code": "ERR_INVALID_ACTION", "data": None, "message": f"无效的鼠标操作: {action}，支持: click/move/scroll/position"}

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("screen_capture", "截图查看效果", "需要确认操作结果时")])
        result["capabilities_used"] = ["pyautogui"]
    return result


def keyboard_control(
    action: Literal["type", "shortcut", "combo"],
    text_or_keys: str,
    interval: float = 0,
) -> Dict[str, Any]:
    """统一键盘控制入口 - 小沈 2026-05-17

    合并 type_text + shortcut + key_combo
    action: "type"|"shortcut"|"combo"
    """
    if action == "type":
        from app.services.tools.desktop.gui_tools import _type_text
        result = _type_text(text=text_or_keys, interval=interval)
    elif action == "shortcut":
        from app.services.tools.desktop.gui_tools import _shortcut
        result = _shortcut(keys=text_or_keys)
    elif action == "combo":
        from app.services.tools.desktop.gui_tools import _key_combo
        key_list = [k.strip() for k in text_or_keys.split(",")]
        result = _key_combo(keys=key_list)
    else:
        return {"code": "ERR_INVALID_ACTION", "data": None, "message": f"无效的键盘操作: {action}，支持: type/shortcut/combo"}

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("screen_capture", "截图查看效果", "需要确认操作结果时")])
        result["capabilities_used"] = ["pyautogui"]
    return result


def screen_capture(
    output_path: Optional[str] = None,
    region: Optional[Dict[str, int]] = None,
    display: Optional[int] = None,
) -> Dict[str, Any]:
    """统一屏幕截图入口 - 小沈 2026-05-17

    合并 screenshot + snapshot
    优先mss（多显示器），降级pyautogui
    当指定display参数时使用snapshot（多显示器），否则使用screenshot
    """
    if display is not None:
        from app.services.tools.desktop.gui_tools import _snapshot
        result = _snapshot(display=display)
    else:
        from app.services.tools.desktop.gui_tools import _screenshot
        result = _screenshot(output_path=output_path, region=region)

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("ocr", "识别截图文字", "需要提取文字时")])
        # 透传gui_tools中的capabilities字段 - 小沈 2026-05-19
        if "capabilities_used" not in result:
            result["capabilities_used"] = ["pyautogui"]
    return result


def clipboard_control(
    action: Literal["read", "write"],
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """统一剪贴板控制入口 - 小沈 2026-05-17

    合并 read_clipboard + write_clipboard
    action: "read"|"write"
    """
    if action == "read":
        from app.services.tools.desktop.gui_tools import _read_clipboard
        result = _read_clipboard()
    elif action == "write":
        if content is None:
            return {"code": "ERR_MISSING_PARAM", "data": None, "message": "写入剪贴板需要提供content参数"}
        from app.services.tools.desktop.gui_tools import _write_clipboard
        result = _write_clipboard(content=content)
    else:
        return {"code": "ERR_INVALID_ACTION", "data": None, "message": f"无效的剪贴板操作: {action}，支持: read/write"}

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("clipboard_control", "验证剪贴板", "需要确认操作结果时")])
    return result
