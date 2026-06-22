# -*- coding: utf-8 -*-
"""
screen_capture — 屏幕截图
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import os
import tempfile
import time as _time_mod
from pathlib import Path
from typing import Dict, Any, Optional

from app.utils.time_utils import timestamp_for_filename
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_SCREENSHOT, ERR_SCREEN_SNAPSHOT


def _build_screen_capture_llm_data(exec_code: str, duration_ms: int, output_path: str = "", region=None,
                                    display: Optional[int] = None, monitor_count: int = 0,
                                    err_code: str = "", detail: str = "") -> dict:
    """screen_capture的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": "截图失败",
            "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "截图失败", "code": err_code or ERR_SCREENSHOT, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    metrics = {}
    if monitor_count > 0:
        metrics["monitors"] = {"value": monitor_count, "text": f"{monitor_count}个"}
    return {
        "summary": f"截图保存到: {output_path}",
        "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": output_path, "params": {"region": region, "display": display}},
        "status": {"exec_code": "success", "message": "截图完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def _screenshot(output_path: str = None, region: Dict[str, int] = None) -> Dict[str, Any]:
    """截取屏幕截图(内聚) — 小健 2026-06-22
    返回原始dict：成功 {"image_path": ...}，失败 {"error_detail": ..., "params": {...}}
    """
    try:
        import pyautogui
    except ImportError:
        return {"error_detail": "pyautogui库未安装", "params": {"library": "pyautogui"}}
    t0 = _time_mod.perf_counter()
    try:
        if output_path is None:
            timestamp = timestamp_for_filename()
            output_path = os.path.join(tempfile.gettempdir(), f"screenshot_{timestamp}.png")

        if region:
            r = (region.get("x", 0), region.get("y", 0), region.get("width", 800), region.get("height", 600))
            img = pyautogui.screenshot(region=r)
        else:
            img = pyautogui.screenshot()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return {"image_path": output_path, "region": region, "duration_ms": int((_time_mod.perf_counter() - t0) * 1000)}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}, "duration_ms": int((_time_mod.perf_counter() - t0) * 1000)}


def _snapshot(display: int = 1) -> Dict[str, Any]:
    """获取完整桌面状态快照(内聚) — 小健 2026-06-22
    返回原始dict：成功 {"image_path": ..., "display": ..., "monitors": ...}，失败 {"error_detail": ..., "params": {...}}
    """
    t0 = _time_mod.perf_counter()
    try:
        import mss
    except ImportError:
        try:
            import pyautogui
            timestamp = timestamp_for_filename()
            output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
            img = pyautogui.screenshot()
            img.save(output_path)
            return {"image_path": output_path, "display": display, "monitors": 0, "duration_ms": int((_time_mod.perf_counter() - t0) * 1000)}
        except ImportError:
            return {"error_detail": "需要安装 mss 或 pyautogui 库", "params": {"libraries": ["mss", "pyautogui"]}}
    try:
        timestamp = timestamp_for_filename()
        output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
        with mss.mss() as sct:
            monitors = sct.monitors
            if display < 1 or display >= len(monitors):
                mon_index = 1
            else:
                mon_index = display
            img = sct.grab(monitors[mon_index])
            from PIL import Image
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(output_path)
        return {"image_path": output_path, "display": display, "monitors": len(monitors) - 1, "duration_ms": int((_time_mod.perf_counter() - t0) * 1000)}
    except Exception as e:
        return {"error_detail": str(e), "params": {"display": display}, "duration_ms": int((_time_mod.perf_counter() - t0) * 1000)}


def screen_capture(output_path: Optional[str] = None, region: Optional[Dict[str, int]] = None, display: Optional[int] = None) -> Dict[str, Any]:
    """统一屏幕截图入口 — 小健 2026-06-22 拆分独立文件"""
    if display is not None:
        result = _snapshot(display=display)
    else:
        result = _screenshot(output_path=output_path, region=region)

    duration_ms = result.pop("duration_ms", 0)

    if "error_detail" in result:
        error_detail = result.pop("error_detail")
        err_params = result.pop("params", {})
        if display is not None:
            err_code = ERR_SCREEN_SNAPSHOT
        else:
            err_code = ERR_SCREENSHOT
        llm_data = _build_screen_capture_llm_data("error", duration_ms, err_code=err_code, detail=error_detail)
        return build_error(data={"error_detail": error_detail, "params": err_params}, llm_data=llm_data)

    image_path = result.pop("image_path", "")
    region_val = result.pop("region", None)
    monitor_count = result.pop("monitors", 0)
    display_val = result.pop("display", None)
    llm_data = _build_screen_capture_llm_data("success", duration_ms, image_path, region=region_val, display=display_val, monitor_count=monitor_count)
    return build_success(data={"image_path": image_path, "display": display_val, "monitors": monitor_count}, llm_data=llm_data)


__all__ = ["screen_capture"]