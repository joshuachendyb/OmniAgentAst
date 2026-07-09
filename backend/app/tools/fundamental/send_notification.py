# -*- coding: utf-8 -*-
"""
send_notification — 发送Windows系统通知
【2026-06-22 小健】从 desktop/desktop_gui_tools.py 迁入 fundamental 为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import asyncio
import concurrent.futures
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_fc_helper import _check_module_available
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_DESKTOP_NOTIFICATION, ERR_NO_WIN10TOAST
from app.tools.validate.file_path_checker import validate_str_param


def _check_module(module_name: str) -> bool:
    """检查Python模块是否已安装 — 小沈 2026-05-18"""
    available, _ = _check_module_available(module_name)
    return available


def _build_send_notification_llm_data(exec_code: str, duration_ms: int, title: str = "",
                                       notif_duration: int = 0, err_code: str = "",
                                       detail: str = "", message: str = "", hint: str = "") -> dict:
    """send_notification的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 加message参数 — 小欧 2026-07-05 加hint参数 — 小欧 2026-07-06 message截断200→50 统一"""
    act_params = {"title": title}
    if message:
        act_params["message"] = message[:50]  # 小欧 2026-07-06 200→50 统一截断
    if notif_duration:
        act_params["duration"] = notif_duration
    if exec_code == "error":
        return {
            "summary": f"发送系统通知，\"{title}\"，失败",
            "action": {"tool": "notify", "tool_zh": "系统通知", "target": title, "params": act_params},
            "status": {"exec_code": "error", "message": "通知发送失败", "code": err_code or ERR_DESKTOP_NOTIFICATION, "detail": detail, "hint": hint if hint else "请检查通知参数和系统通知设置"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"发送系统通知，\"{title}\"，{notif_duration}秒，成功",
        "action": {"tool": "notify", "tool_zh": "系统通知", "target": title, "params": act_params},
        "status": {"exec_code": "success", "message": "通知发送成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def notify(title: str, message: str, duration: int = 5) -> Dict[str, Any]:
    """发送Windows系统通知 — 小健 2026-06-22 迁入fundamental独立文件 — 小健 2026-06-22 修复计时铁规"""
    t0 = _time_mod.perf_counter()
    err = validate_str_param(title, "title")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_send_notification_llm_data("error", duration_ms, title, detail=err, hint="请检查通知标题", message=message)
        return build_error(data={}, llm_data=llm_data)
    err = validate_str_param(message, "message")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_send_notification_llm_data("error", duration_ms, title, detail=err, hint="请检查通知内容", message=message)
        return build_error(data={}, llm_data=llm_data)
    if not _check_module("win10toast"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(data={}, llm_data=_build_send_notification_llm_data("error", duration_ms, title, err_code=ERR_NO_WIN10TOAST, detail="win10toast库未安装", hint="请安装win10toast库", message=message))

    from win10toast import ToastNotifier
    try:
        toaster = ToastNotifier()
        def _show_toast():
            toaster.show_toast(title, message, duration=duration, threaded=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_show_toast)
            future.result(timeout=duration + 5)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {}
        llm_data = _build_send_notification_llm_data("success", duration_ms, title, duration, message=message)
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — title/message/duration 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_send_notification_llm_data("error", duration_ms, title, detail=str(e), hint="发送通知异常，请重试", message=message)
        return build_error(data={}, llm_data=llm_data)


__all__ = ["notify"]