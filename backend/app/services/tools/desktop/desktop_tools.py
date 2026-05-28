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
1. window_info - 窗口信息查询（合并list_windows+get_window_info）
2. window_control - 统一窗口控制（合并set_window_state+focus_window+resize_window）
3. mouse_control - 统一鼠标控制
4. keyboard_control - 统一键盘控制
5. screen_capture - 统一屏幕截图
6. clipboard_control - 统一剪贴板控制

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
from app.utils.tool_result_utils import build_next_actions, truncate_data_for_frontend, make_json_safe  # 小沈 2026-05-20
from app.services.tools._response import build_success, build_error
from app.services.tools.toolhelper.window_helper import check_win32_platform, get_window_rect, get_window_state, find_windows_by_title  # 小沈 2026-05-22


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


def _enum_windows_callback(hwnd: int, windows: List[Dict]) -> bool:
    """枚举窗口回调函数 - 小沈 2026-05-05修正"""
    try:
        if not _win32gui.IsWindowVisible(hwnd):
            return True

        title = _win32gui.GetWindowText(hwnd)
        if not title:
            return True

        rect = get_window_rect(hwnd)
        state = get_window_state(hwnd)

        windows.append({
            "hwnd": hwnd,
            "title": title,
            "state": state,
            "position": rect
        })
    except Exception:
        pass
    return True


def window_info(
    action: str = "list",
    window_title: Optional[str] = None,
    include_minimized: bool = False,
    filter_title: Optional[str] = None,
) -> Dict[str, Any]:
    """统一窗口信息查询 - 小沈 2026-05-22 合并list_windows+get_window_info"""
    err = check_win32_platform()
    if err:
        return err

    if action == "list":
        try:
            windows = []
            _win32gui.EnumWindows(_enum_windows_callback, windows)
            if not include_minimized:
                windows = [w for w in windows if w["state"] != "minimized"]
            if filter_title:
                windows = [w for w in windows if filter_title.lower() in w["title"].lower()]

            return build_success(
                truncate_data_for_frontend({"windows": windows, "total": len(windows)}),
                f"共找到 {len(windows)} 个窗口",
                llm_data={
                    "总数": len(windows),
                    "窗口预览": [{"title": w.get("title","")[:40], "state": w.get("state","")} for w in windows[:20]]
                },
                next_actions=build_next_actions([("window_info", "查询窗口详情", "需要查看特定窗口信息时", {"action": "info", "window_title": "窗口标题"}), ("window_control", "控制窗口", "需要操作窗口时")])
            )
        except Exception as e:
            logger.error(f"window_info list error: {e}")
            return build_error(ERR_WINDOW_LIST, f"获取窗口列表失败: {str(e)}")

    elif action == "info":
        if not window_title:
            return build_error(ERR_PARAM_INVALID, "action=info时必须提供window_title参数",
                next_actions=build_next_actions([("window_info", "列出所有窗口", "查看可用窗口", {"action": "list"})]))
        try:
            matched_hwnds = find_windows_by_title(window_title)
            if not matched_hwnds:
                return build_error(ERR_WINDOW_NOT_FOUND, f"未找到窗口: {window_title}",
                    next_actions=build_next_actions([("window_info", "列出所有窗口", "查看当前打开的窗口", {"action": "list"})]))

            hwnd = matched_hwnds[0]
            title = _win32gui.GetWindowText(hwnd)
            rect = get_window_rect(hwnd)
            state = get_window_state(hwnd)

            try:
                class_name = _win32gui.GetClassName(hwnd)
            except Exception:
                class_name = "Unknown"
            try:
                process_id = _win32api.GetWindowThreadProcessId(hwnd)[0]
            except Exception:
                process_id = 0

            info = {
                "hwnd": hwnd, "title": title, "class_name": class_name,
                "state": state, "position": rect, "process_id": process_id,
                "is_visible": _win32gui.IsWindowVisible(hwnd),
                "is_enabled": _win32gui.IsWindowEnabled(hwnd),
                "matched_count": len(matched_hwnds),
            }
            msg = f"获取窗口信息成功: {title}"
            if len(matched_hwnds) > 1:
                msg += f"（共匹配到 {len(matched_hwnds)} 个窗口，返回第一个）"
            return build_success(info, msg,
                next_actions=build_next_actions([("window_control", "控制该窗口", "需要操作窗口时")]))
        except Exception as e:
            logger.error(f"window_info info error: {e}")
            return build_error(ERR_DESKTOP_GET_WINDOW_INFO, f"获取窗口信息失败: {str(e)}")

    else:
        return build_error(ERR_INVALID_ACTION, f"不支持的action: {action}，可选: list/info",
            next_actions=build_next_actions([("window_info", "查看用法", "确认参数", {"action": "list"})]))


def set_window_state(window_title: str, action: str) -> Dict[str, Any]:
    """设置窗口状态 - 小沈 2026-04-29, 修正 2026-05-05

    【2026-05-17 小沈】保留旧实现，供 window_control 内部调用
    """
    err = check_win32_platform()
    if err:
        return err

    try:
        valid_actions = ["maximize", "minimize", "restore", "topmost", "unpin"]
        if action not in valid_actions:
            return build_error(ERR_INVALID_ACTION, f"无效的操作: {action}，支持的操作为: {valid_actions}")

        matched_hwnds = find_windows_by_title(window_title)

        if not matched_hwnds:
            return build_error(ERR_WINDOW_NOT_FOUND, f"未找到窗口: {window_title}")

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

        return build_success(
            {
                "window_title": title,
                "action": action,
                "hwnd": hwnd,
                "matched_count": len(matched_hwnds),
            },
            msg,
            next_actions=build_next_actions([("window_info", "确认窗口状态", "需要验证操作结果时", {"action": "info", "window_title": title})])
        )

    except Exception as e:
        logger.error(f"set_window_state error: {e}")
        return build_error(ERR_WINDOW_SET_STATE, f"设置窗口状态失败: {str(e)}")


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
        result["next_actions"] = build_next_actions([("window_info", "确认窗口状态", "需要验证操作结果时", {"action": "info", "window_title": window_title})])
    elif result.get("code") != "SUCCESS" and "next_actions" not in result:
        result["next_actions"] = build_next_actions([
            ("window_info", "查看当前窗口列表", "确认窗口名称是否正确时", {"action": "list"}),
            ("tool_help", "查看window_control用法", "不确定参数时", {"tool_name": "window_control"}),
        ])
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
    # ⚠️ 警告: 以下参数已从Schema移除，硬编码默认值，后续视需求决定是否恢复
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
        return build_error(ERR_INVALID_ACTION, f"无效的鼠标操作: {action}，支持: click/move/scroll/position",
            next_actions=build_next_actions([("tool_help", "查看mouse_control参数", "确认可用操作时")]))

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("screen_capture", "截图查看效果", "需要确认操作结果时")])
    elif "next_actions" not in result:
        result["next_actions"] = build_next_actions([
            ("tool_help", "查看mouse_control用法", "不确定参数时", {"tool_name": "mouse_control"}),
            ("screen_capture", "查看当前鼠标位置", "需要确认坐标时"),
        ])
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
        return build_error(ERR_INVALID_ACTION, f"无效的键盘操作: {action}，支持: type/shortcut/combo",
            next_actions=build_next_actions([("tool_help", "查看keyboard_control参数", "确认可用操作时")]))

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("screen_capture", "截图查看效果", "需要确认操作结果时")])
    elif "next_actions" not in result:
        result["next_actions"] = build_next_actions([
            ("tool_help", "查看keyboard_control用法", "不确定参数时", {"tool_name": "keyboard_control"}),
        ])
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
    elif "next_actions" not in result:
        result["next_actions"] = build_next_actions([
            ("tool_help", "查看screen_capture用法", "不确定参数时", {"tool_name": "screen_capture"}),
        ])
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
            return build_error(ERR_MISSING_PARAM, "写入剪贴板需要提供content参数",
                next_actions=build_next_actions([("tool_help", "查看clipboard_control参数", "确认用法时")]))
        from app.services.tools.desktop.gui_tools import _write_clipboard

        result = _write_clipboard(content=content)
    else:
        return build_error(ERR_INVALID_ACTION, f"无效的剪贴板操作: {action}，支持: read/write",
            next_actions=build_next_actions([("tool_help", "查看clipboard_control参数", "确认可用操作时")]))

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("clipboard_control", "验证剪贴板", "需要确认操作结果时")])
    elif "next_actions" not in result:
        result["next_actions"] = build_next_actions([
            ("tool_help", "查看clipboard_control用法", "不确定参数时", {"tool_name": "clipboard_control"}),
        ])
    return result
from app.constants import (
    ERR_DESKTOP_GET_WINDOW_INFO,
    ERR_INVALID_ACTION,
    ERR_MISSING_PARAM,
    ERR_PARAM_INVALID,
    ERR_WINDOW_LIST,
    ERR_WINDOW_NOT_FOUND,
    ERR_WINDOW_SET_STATE,
)
