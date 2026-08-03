# -*- coding: utf-8 -*-
"""
window_resize — 调整窗口大小
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 2026-07-30 - 小欧 - #12:params key"title→window_title" #14:修复标点"成功:,"
# 2026-07-30 - 小欧 - #23:llm_data参数title→window_title; #24:width显式判0; #25:所有调用改关键字参数
# 2026-07-30 - 小欧 - ImportError加logger.error + hint改"工具暂时不能使用:需要安装pywin32库"
# 2026-07-31 - 小欧 - 三堂会审修复B24:MoveWindow返回值未检查,失败假成功→检查后返回ERR_WINDOW_RESIZE
# 2026-07-31 - 小欧 - 三堂会审修复B2:非Windows平台ImportError时提示"仅支持Windows"而非"安装pywin32"
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import platform
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_WINDOW_NOT_FOUND, ERR_WINDOW_RESIZE
from app.tools.validate.file_path_checker import validate_str_param
from app.logger import logger


def _build_window_resize_llm_data(exec_code: str, duration_ms: int, window_title: str = "", width: int = 0, height: int = 0,
                                   err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """window_resize的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 统一_act_params — 小欧 2026-07-05 加hint参数"""
    _act_params = {"width": width, "height": height}
    if window_title:
        _act_params["window_title"] = window_title
    if exec_code == "error":
        return {
            "summary": f"调整窗口大小失败,其窗口标题为 {window_title}",
            "action": {"tool": "window_resize", "tool_zh": "窗口调整", "target": window_title, "params": _act_params},
            "status": {"exec_code": "error", "message": "调整窗口大小失败", "code": err_code or ERR_WINDOW_RESIZE, "detail": detail, "hint": hint if hint else "请检查窗口标题和尺寸"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"调整标题为{window_title}的窗口成功,分辨率为 {width}x{height}",
        "action": {"tool": "window_resize", "tool_zh": "窗口调整", "target": window_title, "params": _act_params},
        "status": {"exec_code": "success", "message": "窗口大小调整完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def window_resize(window_title: str, width: int = 800, height: int = 600) -> Dict[str, Any]:
    """调整窗口大小 — 小健 2026-06-22 拆分独立文件"""
    try:
        import win32gui
    except ImportError:
        if platform.system() != "Windows":
            llm_data = _build_window_resize_llm_data("error", 0, window_title=window_title, err_code=ERR_WINDOW_RESIZE, hint="此功能仅支持Windows系统")
            return build_error(data={}, llm_data=llm_data)
        logger.error("window_resize: pywin32未安装,工具暂时不能使用。请执行: pip install pywin32")
        llm_data = _build_window_resize_llm_data("error", 0, window_title=window_title, err_code="ERR_NO_WIN32GUI", hint="工具暂时不能使用:需要安装pywin32库,请执行: pip install pywin32")
        return build_error(data={}, llm_data=llm_data)
    t0 = _time_mod.perf_counter()
    err = validate_str_param(window_title, "window_title")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_NOT_FOUND, hint="请提供有效的窗口标题,window_title不能为空")
        return build_error(data={}, llm_data=llm_data)
    try:
        target_hwnd = None
        def _enum_cb(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                win_title = win32gui.GetWindowText(hwnd)
                if window_title.lower() in win_title.lower():
                    target_hwnd = hwnd
            return True
        win32gui.EnumWindows(_enum_cb, None)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if not target_hwnd:
            llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_NOT_FOUND, hint="请检查窗口标题是否正确,当前未找到匹配窗口")
            return build_error(data={}, llm_data=llm_data)

        left, top, right, bottom = win32gui.GetWindowRect(target_hwnd)
        curr_width = right - left
        curr_height = bottom - top
        new_width = curr_width if width == 0 else width
        new_height = curr_height if height == 0 else height

        if not win32gui.MoveWindow(target_hwnd, left, top, new_width, new_height, True):
            llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_RESIZE, hint="窗口大小调整失败,可能窗口已关闭或处于最小化状态,请重试")
            return build_error(data={}, llm_data=llm_data)
        data = {"width": new_width, "height": new_height}
        llm_data = _build_window_resize_llm_data("success", duration_ms, window_title=window_title, width=new_width, height=new_height)
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — title/width/height 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, detail=str(e), hint="调整窗口大小时发生异常,请检查窗口状态后重试")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["window_resize"]
