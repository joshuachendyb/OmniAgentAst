# -*- coding: utf-8 -*-
"""
set_window_state — 窗口状态操作(maximize/minimize/restore/topmost/unpin)
【2026-06-22 小健】从window_info.py拆出为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
# 2026-07-30 - 小欧 - #6:hint区分非Windows平台vs缺pywin32库
# 2026-07-30 - 小欧 - #16:msg_fmt死代码改为_; #18:修正多余冒号"为:{→为{"
# 2026-07-30 - 小欧 - 删除未使用的Optional import
# 2026-07-30 - 小欧 - _WINDOW_ACTIONS删除未使用的第三元素(原msg_fmt字符串);解构由func,args,_→func,args
# 2026-07-31 - 小欧 - 三堂会审修复B8:window_title校验失败分支action传""丢失操作名,改传action
# 2026-07-31 - 小欧 - 三堂会审修复B32:移除未使用的List import

import time as _time_mod
from typing import Any, Dict

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_INVALID_ACTION, ERR_WINDOW_NOT_FOUND, ERR_WINDOW_SET_STATE, ERR_DESKTOP_GET_WINDOW_INFO
from app.tools.validate.file_path_checker import validate_str_param
from app.tools.desktop.window_info import (
    check_win32_platform, find_windows_by_title, _win32gui, _win32con,
)


_WINDOW_ACTIONS = {
    "maximize": (_win32gui.ShowWindow, (_win32con.SW_MAXIMIZE,)) if _win32gui else None,
    "minimize": (_win32gui.ShowWindow, (_win32con.SW_MINIMIZE,)) if _win32gui else None,
    "restore": (_win32gui.ShowWindow, (_win32con.SW_RESTORE,)) if _win32gui else None,
    "topmost": (_win32gui.SetWindowPos, (_win32con.HWND_TOPMOST, 0, 0, 0, 0,
              _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE)) if _win32gui else None,
    "unpin": (_win32gui.SetWindowPos, (_win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
            _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE)) if _win32gui else None,
}


def _build_set_window_state_llm_data(exec_code: str, duration_ms: int, action: str, window_title: str = "",
                                      matched_count: int = 0, err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """set_window_state的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 补window_title入_act_params — 小欧 2026-07-05 加hint参数"""
    _act_params = {"action": action}
    if window_title:
        _act_params["window_title"] = window_title
    if exec_code == "error":
        return {
            "summary": f"窗口操作{action}失败:窗口标题为 {window_title}",
            "action": {"tool": "set_window_state", "tool_zh": "窗口状态", "target": window_title, "params": _act_params},
            "status": {"exec_code": "error", "message": f"窗口操作{action}失败", "code": err_code or ERR_WINDOW_SET_STATE, "detail": detail, "hint": hint if hint else "请检查窗口标题和操作类型"},
            "duration_ms": duration_ms, "metrics": {},
        }
    summary = f"窗口操作{action}完成: 窗口标题为{window_title}"
    metrics = {}
    if matched_count > 1:
        summary += f": 匹配{matched_count}个窗口"
        metrics["matched"] = {"value": matched_count, "text": f"{matched_count}个"}
    return {
        "summary": summary,
        "action": {"tool": "set_window_state", "tool_zh": "窗口状态", "target": window_title, "params": _act_params},
        "status": {"exec_code": "success", "message": f"窗口操作{action}成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def set_window_state(window_title: str, action: str) -> Dict[str, Any]:
    """设置窗口状态 — 小健 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    err = validate_str_param(window_title, "window_title")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_WINDOW_NOT_FOUND, detail=err, hint="请提供有效的窗口标题,window_title不能为空")
        return build_error(data={}, llm_data=llm_data)
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        err_msg = err.get("error_detail", "")
        logger.error("set_window_state: %s", err_msg)
        is_platform = "仅支持Windows" in err_msg
        hint = "此功能仅支持Windows系统" if is_platform else "工具暂时不能使用:需要安装pywin32库,请执行: pip install pywin32"
        llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_DESKTOP_GET_WINDOW_INFO, hint=hint)
        return build_error(data={}, llm_data=llm_data)

    try:
        if action not in _WINDOW_ACTIONS or _WINDOW_ACTIONS[action] is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_INVALID_ACTION, hint="请使用支持的操作类型:maximize/minimize/restore/topmost/unpin")
            return build_error(data={}, llm_data=llm_data)

        matched_hwnds = find_windows_by_title(window_title)

        if not matched_hwnds:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_WINDOW_NOT_FOUND, hint="请检查窗口标题是否正确,当前未找到匹配窗口")
            return build_error(data={}, llm_data=llm_data)

        hwnd = matched_hwnds[0]
        title = _win32gui.GetWindowText(hwnd)

        func, args = _WINDOW_ACTIONS[action]
        func(hwnd, *args)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {}
        llm_data = _build_set_window_state_llm_data("success", duration_ms, action, title, len(matched_hwnds))
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data
        # trigger: data 为 {}
        # handler: 直接返回空字符串
        # file:    observation_formatter.py:73-74
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"set_window_state error: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, detail=str(e), hint="窗口操作执行异常,请检查窗口状态后重试")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["set_window_state"]
