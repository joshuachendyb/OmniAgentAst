# -*- coding: utf-8 -*-
"""
send_notification — 发送Windows系统通知
【2026-06-22 小健】从 desktop/desktop_gui_tools.py 迁入 fundamental 为独立文件
"""

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_fc_helper import _check_module_available
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_NOTIFICATION, ERR_NO_WIN10TOAST


def _check_module(module_name: str) -> bool:
    """检查Python模块是否已安装 — 小沈 2026-05-18"""
    available, _ = _check_module_available(module_name)
    return available


def _build_send_notification_llm_data(exec_code: str, duration_ms: int, title: str = "",
                                       notif_duration: int = 0, err_code: str = "",
                                       detail: str = "") -> dict:
    """send_notification的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"通知发送失败: {title}",
            "action": {"tool": "send_notification", "tool_zh": "系统通知", "target": title, "params": {}},
            "status": {"exec_code": "error", "message": "通知发送失败", "code": err_code or ERR_DESKTOP_NOTIFICATION, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"通知已发送: {title}",
        "action": {"tool": "send_notification", "tool_zh": "系统通知", "target": title, "params": {"duration": notif_duration}},
        "status": {"exec_code": "success", "message": "通知发送成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def send_notification(title: str, message: str, duration: int = 5) -> Dict[str, Any]:
    """发送Windows系统通知 — 小健 2026-06-22 迁入fundamental独立文件"""
    if not _check_module("win10toast"):
        return build_error(data={"error_detail": "win10toast库未安装"}, llm_data=_build_send_notification_llm_data("error", 0, title, err_code=ERR_NO_WIN10TOAST))

    from win10toast import ToastNotifier
    t0 = _time_mod.perf_counter()
    try:
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"title": title, "message": message, "duration": duration}
        llm_data = _build_send_notification_llm_data("success", duration_ms, title, duration)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_send_notification_llm_data("error", duration_ms, title, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


__all__ = ["send_notification"]