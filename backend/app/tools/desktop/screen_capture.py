# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-21 - 小欧 - 11.6.1: success分支调 with_artifact_file 声明产出物(截图文件)
"""
screen_capture — 屏幕截图
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 2026-07-30 - 小欧 - #9:修复llm_data summary monitor_count=0时空洞Bug
# 2026-07-30 - 小欧 - #14/#20:dest类型str→Optional[str]; #15:error区分模式; #16/#19:去除_act_params中None值; #17:snapshot except补dest; #18:display=0报错不静默fallback
# 2026-07-30 - 小欧 - #2:hint区分依赖错误vs运行时错误,非依赖错误不再提示安装库
# 2026-07-30 - 小欧 - #7:region/dest类型hint统一Optional; #8:PIL import加ImportError处理
# 2026-07-31 - 小欧 - 三堂会审修复B3:Pillow缺失时hint误导为装mss/pyautogui,改单独提示安装Pillow
# 2026-07-31 - 小欧 - 三堂会审修复B23:data去掉"display": None冗余键(截图模式display_val为空)
# 2026-08-05 - 小欧 - 三堂会审修复#5: dest=""空串绕过主函数校验后 Path("").mkdir() 报含糊错误, _screenshot/_snapshot 的 if dest is None 统一改 if not dest(空串也走临时路径)
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
from app.tools.tool_response import build_success, build_error, with_artifact_file
from app.tools.validate.file_path_checker import validate_path, OpCategory
from app.logger import logger
from app.tools.tool_constants import ERR_SCREENSHOT, ERR_SCREEN_SNAPSHOT


def _build_screen_capture_llm_data(exec_code: str, duration_ms: int, dest: Optional[str] = None, region=None,
                                    display: Optional[int] = None, monitor_count: int = 0,
                                    err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """screen_capture的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 补dest入_act_params — 小欧 2026-07-05 加hint参数"""
    _act_params = {}
    if region is not None:
        _act_params["region"] = region
    if display is not None:
        _act_params["display"] = display
    if dest:
        _act_params["dest"] = dest
    if exec_code == "error":
        is_snapshot = (err_code == ERR_SCREEN_SNAPSHOT)
        mode = "多显示器" if is_snapshot else ""
        summary = f"{mode}截图失败" if mode else "截图失败"
        return {
            "summary": summary,
            "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": "", "params": _act_params},
            "status": {"exec_code": "error", "message": summary, "code": err_code or ERR_SCREENSHOT, "detail": detail, "hint": hint if hint else "请检查屏幕显示设置和权限"},
            "duration_ms": duration_ms, "metrics": {},
        }
    metrics = {}
    if monitor_count > 0:
        metrics["monitors"] = {"value": monitor_count, "text": f"{monitor_count}个"}
        summary = f"截图成功: 已保存到{dest}（{monitor_count}个显示器）"
    else:
        summary = f"截图成功: 已保存到{dest}"
    return {
        "summary": summary,
        "action": {"tool": "screen_capture", "tool_zh": "屏幕截图", "target": dest, "params": _act_params},
        "status": {"exec_code": "success", "message": "截图完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def _screenshot(dest: Optional[str] = None, region: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """截取屏幕截图(内聚) — 小健 2026-06-22
    返回原始dict：成功 {"image_path": ...}，失败 {"error_detail": ..., "params": {...}}
    """
    try:
        import pyautogui
    except ImportError:
        logger.error("screen_capture._screenshot: pyautogui未安装,工具暂时不能使用。请执行: pip install pyautogui")
        return {"error_detail": "pyautogui库未安装,工具暂时不能使用", "params": {"library": "pyautogui"}}
    try:
        if not dest:  # dest为None或空串均生成临时路径 — 2026-08-05 小欧 #5
            timestamp = timestamp_for_filename()
            dest = os.path.join(tempfile.gettempdir(), f"screenshot_{timestamp}.png")

        if region:
            r = (region.get("x", 0), region.get("y", 0), region.get("width", 800), region.get("height", 600))
            img = pyautogui.screenshot(region=r)
        else:
            img = pyautogui.screenshot()

        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        return {"image_path": dest, "region": region}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def _snapshot(display: int = 1, dest: Optional[str] = None) -> Dict[str, Any]:
    """获取完整桌面状态快照(内聚) — 小健 2026-06-22 — 小欧 2026-07-05 修复:接受dest参数
    返回原始dict：成功 {"image_path": ..., "display": ..., "monitors": ...}，失败 {"error_detail": ..., "params": {...}}
    """
    try:
        import mss
    except ImportError:
        try:
            import pyautogui
            if not dest:  # 空串也生成临时路径 — 2026-08-05 小欧 #5
                timestamp = timestamp_for_filename()
                dest = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
            img = pyautogui.screenshot()
            img.save(dest)
            return {"image_path": dest, "display": display, "monitors": 0}
        except ImportError:
            logger.error("screen_capture._snapshot: mss/pyautogui均未安装,工具暂时不能使用。请执行: pip install mss")
            return {"error_detail": "需要安装 mss 或 pyautogui 库,工具暂时不能使用", "params": {"libraries": ["mss", "pyautogui"]}}
    try:
        if not dest:  # 空串也生成临时路径 — 2026-08-05 小欧 #5
            timestamp = timestamp_for_filename()
            dest = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
        with mss.mss() as sct:
            monitors = sct.monitors
            if display < 1 or display >= len(monitors):
                err_params = {"display": display}
                if dest:
                    err_params["dest"] = dest
                return {"error_detail": f"无效的显示器编号: {display}, 有效范围1~{len(monitors)-1}", "params": err_params}
            mon_index = display
            img = sct.grab(monitors[mon_index])
            try:
                from PIL import Image
            except ImportError:
                logger.error("screen_capture._snapshot: Pillow未安装,请执行: pip install Pillow")
                return {"error_detail": "Pillow库未安装,工具暂时不能使用。请执行: pip install Pillow", "params": {"library": "Pillow"}}
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(dest)
        return {"image_path": dest, "display": display, "monitors": len(monitors) - 1}
    except Exception as e:
        params = {"display": display}
        if dest:
            params["dest"] = dest
        return {"error_detail": str(e), "params": params}


def screen_capture(dest: Optional[str] = None, region: Optional[Dict[str, int]] = None, display: Optional[int] = None) -> Dict[str, Any]:
    """统一屏幕截图入口 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    if dest:
        # 工具层校验：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, warn = validate_path(OpCategory.WRITE, dest)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_screen_capture_llm_data("error", duration_ms, dest=dest, region=region, display=display, err_code=ERR_SCREENSHOT, detail=err, hint="请检查输出路径是否合法")
            return build_error(data={}, llm_data=llm_data)
        if warn:
            logger.warning(f"[screen_capture] {warn}")

    if display is not None:
        result = _snapshot(display=display, dest=dest)
    else:
        result = _screenshot(dest=dest, region=region)

    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if "error_detail" in result:
        error_detail = result.pop("error_detail")
        err_params = result.pop("params", {})
        if display is not None:
            err_code = ERR_SCREEN_SNAPSHOT
        else:
            err_code = ERR_SCREENSHOT
        is_dep_error = any(kw in error_detail for kw in ["未安装", "No module named", "ImportError"])
        if "Pillow" in error_detail:
            hint = "工具暂时不能使用:需要安装Pillow库,请执行: pip install Pillow"
        elif is_dep_error:
            hint = "工具暂时不能使用:需要安装依赖库(mss/pyautogui),请执行: pip install mss"
        else:
            hint = "请检查屏幕截图参数和系统权限"
        llm_data = _build_screen_capture_llm_data("error", duration_ms, dest=dest, region=region, display=display, err_code=err_code, detail=error_detail, hint=hint)
        return build_error(data={}, llm_data=llm_data)

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
    with_artifact_file(llm_data, image_path)   # 11.6.1 产出物声明 — 小欧 2026-08-21
    # ---- observation_formatter route -------------------------------------------
    # branch: #21 fallback (key:val)
    # trigger: 无上述20条分支匹配 — image_path/display/monitors 不命中专用分支
    # handler: _format_scalar_data(data) — key | value 单行列表
    # file:    observation_formatter.py:214
    # ------------------------------------------------------------------------------
    data = {"image_path": image_path}
    if display_val is not None:
        data["display"] = display_val
    return build_success(data=data, llm_data=llm_data)


__all__ = ["screen_capture"]
