# -*- coding: utf-8 -*-
"""
screen_capture — 屏幕截图
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import os
import tempfile
import time as _time_mod
from pathlib import Path
from typing import Dict, Any, Optional

from app.utils.time_utils import timestamp_for_filename
from app.tools.tool_response import build_success, build_error
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger
from app.tools.tool_constants import ERR_SCREENSHOT, ERR_SCREEN_SNAPSHOT


def _build_screen_capture_llm_data(exec_code: str, duration_ms: int, output_path: str = "", region=None,
                                    display: Optional[int] = None, monitor_count: int = 0,
                                    err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """screen_capture的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 补output_path入_act_params — 小欧 2026-07-05 加hint参数"""
    _act_params = {"region": region, "display": display}
    if output_path:
        _act_params["output_path"] = output_path
    if exec_code == "error":
        return {
            "summary": "截图失败",
            "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": "", "params": _act_params},
            "status": {"exec_code": "error", "message": "截图失败", "code": err_code or ERR_SCREENSHOT, "detail": detail, "hint": hint if hint else "请检查屏幕显示设置和权限"},
            "duration_ms": duration_ms, "metrics": {},
        }
    metrics = {}
    if monitor_count > 0:
        metrics["monitors"] = {"value": monitor_count, "text": f"{monitor_count}个"}
    monitor_text = f"（{monitor_count}个显示器）" if monitor_count > 0 else ""
    return {
        "summary": f"截图成功: 已保存到{output_path}{monitor_text}",
        "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": output_path, "params": _act_params},
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
        return {"image_path": output_path, "region": region}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def _snapshot(display: int = 1, output_path: str = None) -> Dict[str, Any]:
    """获取完整桌面状态快照(内聚) — 小健 2026-06-22 — 小欧 2026-07-05 修复:接受output_path参数
    返回原始dict：成功 {"image_path": ..., "display": ..., "monitors": ...}，失败 {"error_detail": ..., "params": {...}}
    """
    try:
        import mss
    except ImportError:
        try:
            import pyautogui
            if output_path is None:
                timestamp = timestamp_for_filename()
                output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
            img = pyautogui.screenshot()
            img.save(output_path)
            return {"image_path": output_path, "display": display, "monitors": 0}
        except ImportError:
            return {"error_detail": "需要安装 mss 或 pyautogui 库", "params": {"libraries": ["mss", "pyautogui"]}}
    try:
        if output_path is None:
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
        return {"image_path": output_path, "display": display, "monitors": len(monitors) - 1}
    except Exception as e:
        return {"error_detail": str(e), "params": {"display": display}}


def screen_capture(output_path: Optional[str] = None, region: Optional[Dict[str, int]] = None, display: Optional[int] = None) -> Dict[str, Any]:
    """统一屏幕截图入口 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    if output_path:
        # 工具层校验：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, warn = validate_path(OpCategory.WRITE, output_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_screen_capture_llm_data("error", duration_ms, output_path=output_path, region=region, display=display, err_code=ERR_SCREENSHOT, detail=err, hint="请检查输出路径是否合法")
            return build_error(data={"error_detail": err, "params": {"output_path": output_path}}, llm_data=llm_data)
        if warn:
            logger.warning(f"[screen_capture] {warn}")

    if display is not None:
        result = _snapshot(display=display, output_path=output_path)
    else:
        result = _screenshot(output_path=output_path, region=region)

    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if "error_detail" in result:
        error_detail = result.pop("error_detail")
        err_params = result.pop("params", {})
        if display is not None:
            err_code = ERR_SCREEN_SNAPSHOT
        else:
            err_code = ERR_SCREENSHOT
        llm_data = _build_screen_capture_llm_data("error", duration_ms, output_path=output_path, region=region, display=display, err_code=err_code, detail=error_detail, hint="请检查屏幕显示设置或安装必要的依赖库(mss/pyautogui)")
        return build_error(data={"error_detail": error_detail, "params": err_params}, llm_data=llm_data)

    image_path = result.pop("image_path", "")
    region_val = result.pop("region", None)
    # =============================================================================
    # 数据设计：monitors 从 data pop 出，通过 llm_data.metrics 传入 summary
    # summary 示例: "截图保存到: /path/screenshot.png（2个显示器）"
    # — 小欧 2026-07-06 18:46:13
    # =============================================================================
    monitor_count = result.pop("monitors", 0)
    display_val = result.pop("display", None)
    llm_data = _build_screen_capture_llm_data("success", duration_ms, image_path, region=region_val, display=display_val, monitor_count=monitor_count)
    # ---- observation_formatter route -------------------------------------------
    # branch: #21 fallback (key:val)
    # trigger: 无上述20条分支匹配 — image_path/display/monitors 不命中专用分支
    # handler: _format_scalar_data(data) — key | value 单行列表
    # file:    observation_formatter.py:214
    # ------------------------------------------------------------------------------
    return build_success(data={"image_path": image_path, "display": display_val}, llm_data=llm_data)


__all__ = ["screen_capture"]