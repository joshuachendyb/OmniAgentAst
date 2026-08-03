# -*- coding: utf-8 -*-
"""
keyboard_control — 键盘控制
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
# 2026-07-30 - 小欧 - #9:hint区分依赖错误vs运行时错误,统一格式
# 2026-07-30 - 小欧 - llm_data error status.message从"无效的键盘操作"改为"键盘操作失败"(action实际有效)
# 2026-07-30 - 小欧 - 删除未使用的List/ERR_KEY_COMBO import;helper error_detail去掉冗余安装提示(主函数hint已有)
# 2026-07-30 - 小欧 - 删除未使用的_key_combo函数(内嵌List[str]但List import已删,会NameError)
import time as _time_mod
from typing import Dict, Any, Literal

from app.tools.tool_response import build_success, build_error
from app.tools.desktop.desktop_register import check_pyautogui_available
from app.tools.tool_constants import ERR_INVALID_ACTION, ERR_KEYBOARD_TYPE, ERR_KEYBOARD_SHORTCUT
from app.logger import logger


def _build_keyboard_control_llm_data(exec_code: str, duration_ms: int, action: str, text_or_keys: str,
                                      err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """keyboard_control的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 补text_or_keys — 小欧 2026-07-05 加hint参数"""
    _act_params = {"action": action}
    if text_or_keys:
        _act_params["text_or_keys"] = text_or_keys
    if exec_code == "error":
        return {
            "summary": f"键盘{action}，失败: {detail}",
            "action": {"tool": "keyboard_control", "tool_zh": "键盘控制", "target": action, "params": _act_params},
            "status": {"exec_code": "error", "message": f"键盘操作{action}失败", "code": err_code or ERR_INVALID_ACTION, "detail": detail, "hint": hint if hint else "请使用支持的操作类型"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"键盘{action}，成功",
        "action": {"tool": "keyboard_control", "tool_zh": "键盘控制", "target": action, "params": _act_params},
        "status": {"exec_code": "success", "message": "键盘操作完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _type_text(text: str, interval: float = 0) -> Dict[str, Any]:
    """模拟键盘输入文本(内聚) — 小健 2026-06-22"""
    if not check_pyautogui_available():
        logger.error("keyboard_control._type_text: pyautogui未安装,工具暂时不能使用。请执行: pip install pyautogui")
        return {"error_detail": "pyautogui库未安装", "params": {"library": "pyautogui"}}
    try:
        import pyautogui
        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            pyautogui.write(text)
        return {"text_length": len(text)}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def _shortcut(keys: str) -> Dict[str, Any]:
    """执行键盘快捷键组合(内聚) — 小健 2026-06-22"""
    if not check_pyautogui_available():
        logger.error("keyboard_control._shortcut: pyautogui未安装,工具暂时不能使用。请执行: pip install pyautogui")
        return {"error_detail": "pyautogui库未安装", "params": {"library": "pyautogui"}}
    try:
        import pyautogui
        key_list = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        return {"keys": keys}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "pyautogui"}}


def keyboard_control(action: Literal["type", "shortcut"], text_or_keys: str) -> Dict[str, Any]:
    """统一键盘控制入口 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-24 参数简化
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    t0 = _time_mod.perf_counter()
    
    if not isinstance(text_or_keys, str) or not text_or_keys.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_keyboard_control_llm_data("error", duration_ms, action, text_or_keys, hint="请提供非空的键盘输入内容")
        return build_error(data={}, llm_data=llm_data)
    if action == "type":
        result = _type_text(text=text_or_keys, interval=0)
    elif action == "shortcut":
        result = _shortcut(keys=text_or_keys)
    else:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_keyboard_control_llm_data("error", duration_ms, action, text_or_keys, hint="请使用type或shortcut作为action参数")
        return build_error(data={}, llm_data=llm_data)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if "error_detail" in result:
        err_code = {
            "type": ERR_KEYBOARD_TYPE,
            "shortcut": ERR_KEYBOARD_SHORTCUT,
        }.get(action, ERR_INVALID_ACTION)
        is_dep_error = any(kw in result["error_detail"] for kw in ["未安装", "No module named", "ImportError"])
        hint = "工具暂时不能使用:需要安装pyautogui库,请执行: pip install pyautogui" if is_dep_error else "请检查键盘操作参数是否正确"
        llm_data = _build_keyboard_control_llm_data("error", duration_ms, action, text_or_keys, err_code=err_code, detail=result["error_detail"], hint=hint)
        return build_error(data={}, llm_data=llm_data)
    
    llm_data = _build_keyboard_control_llm_data("success", duration_ms, action, text_or_keys)
    # ---- observation_formatter route -------------------------------------------
    # branch: #21 fallback (key:val) — type 或 shortcut
    # trigger: 无上述20条分支匹配 — text_length(typing) 或 keys(shortcut)
    # handler: _format_scalar_data(data) — key | value 单行列表
    # file:    observation_formatter.py:214
    # ------------------------------------------------------------------------------
    return build_success(data=result, llm_data=llm_data)


__all__ = ["keyboard_control"]
