# -*- coding: utf-8 -*-
"""
window_focus — 聚焦窗口
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 2026-07-30 - 小欧 - #10:修复错别字"围为→为" #11:params key"title→window_title"
# 2026-07-30 - 小欧 - #21:llm_data参数title→window_title对齐schema; #22:所有调用改关键字参数
# 2026-07-30 - 小欧 - ImportError加logger.error + hint改"工具暂时不能使用:需要安装pywin32库"
# 2026-07-31 - 小欧 - 三堂会审修复B9:SetForegroundWindow返回值未检查,失败假成功→检查后返回ERR_FOCUS_WINDOW
# 2026-07-31 - 小欧 - 三堂会审修复B2:非Windows平台ImportError时提示"仅支持Windows"而非"安装pywin32"
# 2026-07-31 - 小欧 - CRITICAL: 补充缺失的 ERR_NO_WIN32GUI 导入(第21行), 原缺导入导致非Windows/无pywin32环境时 NameError 崩溃
# 2026-08-05 - 小欧 - 三堂会审修复#2: 多窗口匹配取"最后一个"改"第一个"(匹配到即停止枚举), 与 set_window_state 取 matched_hwnds[0] 行为一致, 消除同标题多窗口时行为不可预期
# 2026-08-05 - 小欧 - 三堂会审修复#10: "ERR_INVALID_PARAM"字符串字面量→ERR_INVALID_PARAMS常量(注意常量带S), 与同文件ERR_FOCUS_WINDOW/ERR_WINDOW_NOT_FOUND常量风格统一
# 2026-08-11 - 小欧 - task002 三堂会审修复B(问题B): ERR_FOCUS_WINDOW hint 文案改三段式引导
#   —— ①先 set_window_state(action='restore') 还原窗口后重试 → ②仍失败重试一次 → ③再失败需用户手动点击激活。
#   背景: 原"先点击桌面"建议实测无效(Windows 前台锁定仅真实用户输入可解除, pyautogui 模拟点击不产生真实输入事件,
#   实测 mouse_click 先行成功 window_focus 仍失败), 会引导 LLM 空转, 与 retry_engine hint 语义(提供真实可用的下一步)相悖
# 2026-08-11 - 小欧 - 三堂会审复核修复(问题1/问题2): ①自写 _enum_cb EnumWindows 循环改复用 find_windows_by_title(DRY, 与 window_resize 对齐, 匹配语义不变: 可见+包含匹配+取第一个)
#   ②函数内 try-import win32gui + platform.system() 改 check_win32_platform(与 window_resize/set_window_state 模式一致, 统一窗口工具平台/依赖检测)
#   ③非Windows平台错误码 ERR_NO_WIN32GUI 改 ERR_FOCUS_WINDOW(码与hint语义对齐, 与 window_resize 平台场景用 ERR_WINDOW_RESIZE 同理)
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_FOCUS_WINDOW, ERR_WINDOW_NOT_FOUND, ERR_NO_WIN32GUI, ERR_INVALID_PARAMS  # 2026-08-05 小欧 #9: 补缺失的 ERR_NO_WIN32GUI(原缺导入导致 NameError 崩溃); 2026-08-05 #10: ERR_INVALID_PARAM字符串→ERR_INVALID_PARAMS常量
from app.tools.desktop.window_info import check_win32_platform, find_windows_by_title, _win32gui  # 2026-08-11 小欧: 复用共享实现(DRY), 替代自写EnumWindows/函数内try-import, 与 window_resize 对齐
from app.logger import logger


def _build_window_focus_llm_data(exec_code: str, duration_ms: int, window_title: str = "",
                                  err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """window_focus的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    if exec_code == "error":
        return {
            "summary": f"聚焦窗口失败,其窗口标题为 {window_title}",
            "action": {"tool": "window_focus", "tool_zh": "窗口聚焦", "target": window_title, "params": {"window_title": window_title}},
            "status": {"exec_code": "error", "message": "聚焦窗口失败", "code": err_code or ERR_FOCUS_WINDOW, "detail": detail, "hint": hint if hint else "请检查窗口标题是否正确"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"窗口已聚焦: 其窗口标题为 {window_title}",
        "action": {"tool": "window_focus", "tool_zh": "窗口聚焦", "target": window_title, "params": {"window_title": window_title}},
        "status": {"exec_code": "success", "message": "窗口聚焦完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def window_focus(window_title: str) -> Dict[str, Any]:
    """聚焦窗口 — 小健 2026-06-22 拆分独立文件 — 小欧 2026-08-11 复用find_windows_by_title+check_win32_platform"""
    t0 = _time_mod.perf_counter()
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        err_msg = err.get("error_detail", "")
        logger.error("window_focus: %s", err_msg)
        is_platform = "仅支持Windows" in err_msg
        err_code = ERR_FOCUS_WINDOW if is_platform else ERR_NO_WIN32GUI
        hint = "此功能仅支持Windows系统" if is_platform else "工具暂时不能使用:需要安装pywin32库,请执行: pip install pywin32"
        llm_data = _build_window_focus_llm_data("error", duration_ms, window_title=window_title, err_code=err_code, hint=hint)
        return build_error(data={}, llm_data=llm_data)
    if not window_title or not isinstance(window_title, str) or not window_title.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_focus_llm_data("error", duration_ms, window_title="", err_code=ERR_INVALID_PARAMS, detail="window_title不能为空", hint="请提供有效的窗口标题,window_title不能为空")
        return build_error(data={}, llm_data=llm_data)
    try:
        matched_hwnds = find_windows_by_title(window_title)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if not matched_hwnds:
            llm_data = _build_window_focus_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_NOT_FOUND, hint="请检查窗口标题是否正确,当前未找到匹配窗口")
            return build_error(data={}, llm_data=llm_data)

        target_hwnd = matched_hwnds[0]
        if not _win32gui.SetForegroundWindow(target_hwnd):
            llm_data = _build_window_focus_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_FOCUS_WINDOW, hint="窗口未能被聚焦: ①请先调用 set_window_state(action='restore') 还原该窗口后重试; ②若仍失败,窗口可能被系统前台锁定,需用户手动点击该窗口激活后再试")
            return build_error(data={}, llm_data=llm_data)
        data = {}
        llm_data = _build_window_focus_llm_data("success", duration_ms, window_title=window_title)
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data
        # trigger: data 为 {}
        # handler: 直接返回空字符串
        # file:    observation_formatter.py:73-74
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_focus_llm_data("error", duration_ms, window_title=window_title, detail=str(e), hint="聚焦窗口时发生异常,请检查窗口状态后重试")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["window_focus"]
