# -*- coding: utf-8 -*-
"""
DESKTOP Tools - 桌面工具实现(窗口管理)
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【架构规范】2026-04-29 小沈

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件:
1. *_tools.py: 函数实现(必须有详细注释)
2. *_schema.py: Pydantic 模型(输入参数定义)
3. *_register.py: 显式注册(description + examples + input_model)

【工具列表】窗口管理工具
1. window_info - 窗口信息查询(合并list_windows+get_window_info)
2. window_control - 统一窗口控制(合并set_window_state+focus_window+resize_window)
3. mouse_control - 统一鼠标控制
4. keyboard_control - 统一键盘控制
5. screen_capture - 统一屏幕截图
6. clipboard_control - 统一剪贴板控制

创建时间: 2026-04-29
【修正 2026-05-05 小沈】小健检查发现的问题:
1. pywin32未安装/非Windows时模块加载崩溃 → 改为try/except惰性导入 + HAS_WIN32标志
2. 裸except(7处) → 改为 except Exception
3. 错误码"ERROR" → 统一为 ERR_XXX
4. 多窗口匹配只取第一个 → 加 matched_count 提示
5. action缺少枚举约束 → Schema改Literal(在schema.py中)
6. 删除死代码 target_hwnd / _is_window_visible
7. 重复定义 find_window_callback → 抽取 _find_windows_by_title 公共函数
"""

import platform
import time as _time_mod
from typing import Any, Dict, List, Optional, Literal
from app.utils.logger import logger
from app.utils.tool_result_formatter import truncate_data_for_frontend, make_json_safe
from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.window_helper import check_win32_platform, get_window_rect, get_window_state, find_windows_by_title
from app.constants import (
    ERR_DESKTOP_GET_WINDOW_INFO,
    ERR_INVALID_ACTION,
    ERR_MISSING_PARAM,
    ERR_PARAM_INVALID,
    ERR_WINDOW_LIST,
    ERR_WINDOW_NOT_FOUND,
    ERR_WINDOW_SET_STATE,
)


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
        logger.warning("pywin32未安装,桌面工具将不可用。请执行: pip install pywin32")


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


def _build_window_info_llm(exec_code: str, duration_ms: int, window_count: int, filter_title: str = "") -> dict:
    """window_info的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"获取窗口列表失败",
            "action": {"tool": "window_info", "tool_zh": "窗口信息", "target": filter_title or "全部", "params": {"filter_title": filter_title}},
            "status": {"exec_code": "error", "message": "获取窗口列表失败", "code": ERR_WINDOW_LIST, "detail": "", "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"共找到 {window_count} 个窗口",
        "action": {"tool": "window_info", "tool_zh": "窗口信息", "target": filter_title or "全部", "params": {"filter_title": filter_title}},
        "status": {"exec_code": "success", "message": "获取窗口列表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"windows": {"value": window_count, "text": f"{window_count}个"}},
    }


def _build_set_window_state_llm(exec_code: str, duration_ms: int, action: str, window_title: str = "",
                                 matched_count: int = 0, err_code: str = "", detail: str = "") -> dict:
    """set_window_state的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"窗口操作{action}失败: {window_title}",
            "action": {"tool": "set_window_state", "tool_zh": "窗口状态", "target": window_title, "params": {"action": action}},
            "status": {"exec_code": "error", "message": f"窗口操作{action}失败", "code": err_code or ERR_WINDOW_SET_STATE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    summary = f"窗口操作{action}完成: {window_title}"
    metrics = {}
    if matched_count > 1:
        summary += f"(匹配{matched_count}个窗口)"
        metrics["matched"] = {"value": matched_count, "text": f"{matched_count}个"}
    return {
        "summary": summary,
        "action": {"tool": "set_window_state", "tool_zh": "窗口状态", "target": window_title, "params": {"action": action}},
        "status": {"exec_code": "success", "message": f"窗口操作{action}成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def window_info(
    include_minimized: bool = False,
    filter_title: Optional[str] = None,
) -> Dict[str, Any]:
    """列出所有窗口 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_info_llm("error", duration_ms, 0, filter_title or "")
        return build_error(data={"error_detail": "桌面工具不可用"}, llm_data=llm_data)

    try:
        windows = []
        _win32gui.EnumWindows(_enum_windows_callback, windows)
        if not include_minimized:
            windows = [w for w in windows if w["state"] != "minimized"]
        if filter_title:
            windows = [w for w in windows if filter_title.lower() in w["title"].lower()]

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = truncate_data_for_frontend({"windows": windows, "total": len(windows)})
        llm_data = _build_window_info_llm("success", duration_ms, len(windows), filter_title or "")
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        logger.error(f"window_info list error: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_info_llm("error", duration_ms, 0, filter_title or "")
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


_WINDOW_ACTIONS = {
    "maximize": (_win32gui.ShowWindow, (_win32con.SW_MAXIMIZE,), "已最大化窗口"),
    "minimize": (_win32gui.ShowWindow, (_win32con.SW_MINIMIZE,), "已最小化窗口"),
    "restore":  (_win32gui.ShowWindow, (_win32con.SW_RESTORE,), "已还原窗口"),
    "topmost":  (_win32gui.SetWindowPos, (_win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                          _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE), "已置顶窗口"),
    "unpin":    (_win32gui.SetWindowPos, (_win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                          _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE), "已取消置顶窗口"),
}


def set_window_state(window_title: str, action: str) -> Dict[str, Any]:
    """设置窗口状态 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_set_window_state_llm("error", duration_ms, action, window_title, err_code=ERR_DESKTOP_GET_WINDOW_INFO)
        return build_error(data={"error_detail": "桌面工具不可用"}, llm_data=llm_data)

    try:
        if action not in _WINDOW_ACTIONS:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_set_window_state_llm("error", duration_ms, action, window_title, err_code=ERR_INVALID_ACTION)
            return build_error(data={"error_detail": f"无效的操作: {action}", "action": action}, llm_data=llm_data)

        matched_hwnds = find_windows_by_title(window_title)

        if not matched_hwnds:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_set_window_state_llm("error", duration_ms, action, window_title, err_code=ERR_WINDOW_NOT_FOUND)
            return build_error(data={"error_detail": f"未找到窗口: {window_title}", "window_title": window_title}, llm_data=llm_data)

        hwnd = matched_hwnds[0]
        title = _win32gui.GetWindowText(hwnd)

        func, args, msg_fmt = _WINDOW_ACTIONS[action]
        func(hwnd, *args)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"window_title": title, "action": action, "hwnd": hwnd, "matched_count": len(matched_hwnds)}
        llm_data = _build_set_window_state_llm("success", duration_ms, action, title, len(matched_hwnds))
        return build_success(data=data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"set_window_state error: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_set_window_state_llm("error", duration_ms, action, window_title, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


# ========== 窗口控制 — 7个独立函数 ==========

def window_focus(window_title: str) -> Dict[str, Any]:
    """聚焦窗口 — 小欧 2026-06-17"""
    from app.tools.desktop.desktop_gui_tools import _focus_window
    return _focus_window(window_title)


def window_resize(window_title: str, width: int = 800, height: int = 600) -> Dict[str, Any]:
    """调整窗口大小 — 小欧 2026-06-17"""
    from app.tools.desktop.desktop_gui_tools import _resize_window
    result = _resize_window(window_title, width=width, height=height)
    return result


def window_maximize(window_title: str) -> Dict[str, Any]:
    """最大化窗口 — 小欧 2026-06-17"""
    result = set_window_state(window_title, "maximize")
    return result


def window_minimize(window_title: str) -> Dict[str, Any]:
    """最小化窗口 — 小欧 2026-06-17"""
    result = set_window_state(window_title, "minimize")
    return result


def window_restore(window_title: str) -> Dict[str, Any]:
    """还原窗口 — 小欧 2026-06-17"""
    result = set_window_state(window_title, "restore")
    return result


def window_topmost(window_title: str) -> Dict[str, Any]:
    """窗口置顶 — 小欧 2026-06-17"""
    result = set_window_state(window_title, "topmost")
    return result


def window_unpin(window_title: str) -> Dict[str, Any]:
    """取消窗口置顶 — 小欧 2026-06-17"""
    result = set_window_state(window_title, "unpin")
    return result


# ========== 鼠标控制 — 4个独立函数 ==========

def mouse_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> Dict[str, Any]:
    """鼠标单击 — 小欧 2026-06-17"""
    click_type = "single"
    from app.tools.desktop.desktop_gui_tools import _click
    return _click(x=x, y=y, button=button, click_type=click_type)


def mouse_move(x: int, y: int) -> Dict[str, Any]:
    """移动鼠标到指定位置 — 小欧 2026-06-17"""
    duration = 0
    from app.tools.desktop.desktop_gui_tools import _move
    return _move(x=x, y=y, duration=duration)


def mouse_scroll(direction: str = "down", amount: int = 3) -> Dict[str, Any]:
    """鼠标滚轮滚动 — 小欧 2026-06-17"""
    from app.tools.desktop.desktop_gui_tools import _scroll
    return _scroll(direction=direction, amount=amount)


def mouse_position() -> Dict[str, Any]:
    """获取鼠标当前位置 — 小欧 2026-06-17"""
    from app.tools.toolhelper.gui_helper import _get_mouse_position
    return _get_mouse_position()


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
        from app.tools.desktop.desktop_gui_tools import _type_text
        result = _type_text(text=text_or_keys, interval=interval)
    elif action == "shortcut":
        from app.tools.desktop.desktop_gui_tools import _shortcut
        result = _shortcut(keys=text_or_keys)
    elif action == "combo":
        from app.tools.desktop.desktop_gui_tools import _key_combo
        key_list = [k.strip() for k in text_or_keys.split(",")]
        result = _key_combo(keys=key_list)
    else:
        return build_error(ERR_INVALID_ACTION, f"无效的键盘操作: {action},支持: type/shortcut/combo", data={"action": action})

    return result


def screen_capture(
    output_path: Optional[str] = None,
    region: Optional[Dict[str, int]] = None,
    display: Optional[int] = None,
) -> Dict[str, Any]:
    """统一屏幕截图入口 - 小沈 2026-05-17

    合并 screenshot + snapshot
    优先mss(多显示器),降级pyautogui
    当指定display参数时使用snapshot(多显示器),否则使用screenshot
    """
    if display is not None:
        from app.tools.desktop.desktop_gui_tools import _snapshot
        result = _snapshot(display=display)
    else:
        from app.tools.desktop.desktop_gui_tools import _screenshot
        result = _screenshot(output_path=output_path, region=region)

    return result


def clipboard_read() -> Dict[str, Any]:
    """读取剪贴板内容 — 小欧 2026-06-17"""
    from app.tools.desktop.desktop_gui_tools import _read_clipboard
    return _read_clipboard()


def clipboard_write(content: str) -> Dict[str, Any]:
    """写入内容到剪贴板 — 小欧 2026-06-17"""
    from app.tools.desktop.desktop_gui_tools import _write_clipboard
    return _write_clipboard(content=content)

