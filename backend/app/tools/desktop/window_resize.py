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
# 2026-08-05 - 小欧 - 三堂会审修复#2: 多窗口匹配取"最后一个"改"第一个"(匹配到即停止枚举), 与 set_window_state 行为一致; 修复#8 schema width/height 加 ge=0; 修复#9 "ERR_NO_WIN32GUI"字符串→常量
# 2026-08-05 - 小欧 - 三堂会审复核: width/height补运行时校验(负数/None/非int), 防直接调函数绕过schema ge=0, 与mouse_click/mouse_scroll"schema+运行时双重防御"口径一致
# 2026-08-11 - 小欧 - task002 三堂会审修复A(问题A): ①自写EnumWindows循环改复用 find_windows_by_title(DRY, 匹配语义不变: 可见+包含匹配+取第一个)
#   ②check_win32_platform 替代函数内 try-import win32gui(与 set_window_state 模式一致, 统一窗口工具平台/依赖检测)
#   ③最小化窗口自恢复: IsIconic→ShowWindow(SW_RESTORE)→二次校验 not IsIconic(对齐 set_window_state 的 _window_state_reached 口径)→再 MoveWindow;
#     restore 失败返回 ERR_WINDOW_RESIZE 并提示先调用 set_window_state(action='restore')(最小化窗口 MoveWindow 必失败, restore 是完成 resize 的必要前置, 不越权)
# 2026-08-11 - 小欧 - 三堂会审修复A(实施中暴露的关联BUG, 一并修复): pywin32 的 win32gui.MoveWindow 返回 None(非BOOL),
#   原 2026-07-31 B24 修复 `if not MoveWindow(...)` 恒真→所有 window_resize 假失败(实测 MoveWindow 实际成功且窗口尺寸已达目标, 但返回 None)。
#   改法与 set_window_state 的 _window_state_reached 口径一致: 操作后验证最终状态——GetWindowRect 尺寸精确等于目标值(width/height, 0表示保持原尺寸)。
#   [验证] 真实tk窗口: MoveWindow(1000x700)后 GetWindowRect 实际 (1100-100, 800-100) 精确匹配 ✓
# 2026-08-13 - 小欧 - 三堂会审修复#12: ShowWindow(SW_RESTORE)跨进程异步, 还原后立即IsIconic可能仍True→误报restore失败且永不MoveWindow(最小化窗口缩不了)
#   【病根】L95-99 restore后单次IsIconic重判, 未等待窗口还原完成(Windows窗口状态变更异步)
#   【改法】轮询等待还原完成(最多10次*0.05s≈0.5s), 循环内break提前退出; 超时仍未还原才返回ERR_WINDOW_RESIZE
# 2026-08-13 - 小欧 - 三堂会审修复#13: 最大化窗口(IsZoomed)MoveWindow忽略尺寸, 精确相等判定恒失败
#   【病根】IsIconic=False跳过还原块, MoveWindow对最大化窗口尺寸无效; 且WM_GETMINMAXINFO钳制下请求<窗口最小尺寸也精确相等失败(Notepad/对话框等)
#   【改法】①IsZoomed=True时先ShowWindow(SW_RESTORE)降级为普通态再MoveWindow; ②验证改"接近"判定(_r2-_l2>=new_width-2), 接受系统min/max钳制
# 2026-08-13 - 小欧 - 三堂会审修复#33: 空window_title返回ERR_WINDOW_NOT_FOUND(窗口未找到), window_focus.py:74同条件返ERR_INVALID_PARAMS, 两工具同参数同校验口径不一
#   【病根】参数非法被误标"未找到", 误导LLM/前端判断
#   【改法】统一为ERR_INVALID_PARAMS(参数非法优先于未找到), 与window_focus对齐
# 2026-08-13 - 小欧 - 三堂会审复核#13修复方法(老陈要求): 原resize_ok单向判定(_r2-_l2>=new_width-2)只防大不防小,
#   缩小请求完全失败(MoveWindow无效, 实际尺寸=旧尺寸>目标)时恒真误判成功; 改"精确达目标(容差2) 或
#   尺寸确实发生变化"双条件, 保留钳制容忍的同时检出缩小失败(模拟8场景实证: 修复OLD两处X!无新退化)
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_WINDOW_NOT_FOUND, ERR_WINDOW_RESIZE, ERR_NO_WIN32GUI, ERR_INVALID_PARAMS  # 2026-08-05 小欧 #9: 补ERR_NO_WIN32GUI导入, 原用字符串字面量; 2026-08-13 #33: 补ERR_INVALID_PARAMS(空标题参数非法)
from app.tools.validate.file_path_checker import validate_str_param
from app.tools.desktop.window_info import check_win32_platform, find_windows_by_title, _win32gui, _win32con  # 2026-08-11 小欧: 复用共享实现(DRY), 替代自写EnumWindows/局部import
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
    """调整窗口大小 — 小健 2026-06-22 拆分独立文件 — 小欧 2026-08-11 复用find_windows_by_title+IsIconic最小化自恢复"""
    t0 = _time_mod.perf_counter()
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        err_msg = err.get("error_detail", "")
        logger.error("window_resize: %s", err_msg)
        is_platform = "仅支持Windows" in err_msg
        err_code = ERR_WINDOW_RESIZE if is_platform else ERR_NO_WIN32GUI
        hint = "此功能仅支持Windows系统" if is_platform else "工具暂时不能使用:需要安装pywin32库,请执行: pip install pywin32"
        llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=err_code, hint=hint)
        return build_error(data={}, llm_data=llm_data)
    err = validate_str_param(window_title, "window_title")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_INVALID_PARAMS, hint="请提供有效的窗口标题,window_title不能为空")
        return build_error(data={}, llm_data=llm_data)
    # 2026-08-05 小欧: width/height 运行时校验(防直接调函数绕过 schema ge=0)
    if (not isinstance(width, int) or isinstance(width, bool) or width < 0
            or not isinstance(height, int) or isinstance(height, bool) or height < 0):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_resize_llm_data(
            "error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_RESIZE,
            detail="width/height必须为非负整数,传0表示不修改保持原尺寸",
            hint="请提供有效的窗口尺寸:width/height必须为0或正整数")
        return build_error(data={}, llm_data=llm_data)
    try:
        matched_hwnds = find_windows_by_title(window_title)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if not matched_hwnds:
            llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_NOT_FOUND, hint="请检查窗口标题是否正确,当前未找到匹配窗口")
            return build_error(data={}, llm_data=llm_data)

        target_hwnd = matched_hwnds[0]
        # 2026-08-11 小欧 三堂会审修复A: 最小化窗口 MoveWindow 必失败, 先 restore
        # (对齐 set_window_state 口径: ShowWindow(SW_RESTORE) 后验证 not IsIconic)
        # 2026-08-13 小欧 三堂会审修复#12: ShowWindow异步(跨进程), 还原后立即IsIconic可能仍为True→误报restore失败;
        #   改轮询等待还原完成(最多10次*0.05s≈0.5s)再判, 消除跨进程竞态
        if _win32gui.IsIconic(target_hwnd):
            _win32gui.ShowWindow(target_hwnd, _win32con.SW_RESTORE)
            for _ in range(10):
                if not _win32gui.IsIconic(target_hwnd):
                    break
                _time_mod.sleep(0.05)
            else:
                llm_data = _build_window_resize_llm_data("error", duration_ms, window_title=window_title, err_code=ERR_WINDOW_RESIZE, hint="窗口还原(restore)失败,无法调整最小化窗口大小,请先调用 set_window_state(action='restore') 还原后重试")
                return build_error(data={}, llm_data=llm_data)
        # 2026-08-13 小欧 三堂会审修复#13: 最大化窗口IsZoomed=True时IsIconic=False跳过还原块, MoveWindow对最大化窗口忽略尺寸→恒失败;
        #   先降级为普通态(ShowWindow(SW_RESTORE))再MoveWindow, 符合Windows窗口管理语义
        if _win32gui.IsZoomed(target_hwnd):
            _win32gui.ShowWindow(target_hwnd, _win32con.SW_RESTORE)

        left, top, right, bottom = _win32gui.GetWindowRect(target_hwnd)
        curr_width = right - left
        curr_height = bottom - top
        new_width = curr_width if width == 0 else width
        new_height = curr_height if height == 0 else height

        # 2026-08-11 小欧 三堂会审修复A(实施中暴露关联BUG): pywin32 MoveWindow 返回 None(非BOOL),
        # 原 `if not MoveWindow(...)` 恒真→所有 resize 假失败。改法与 set_window_state 口径一致:
        # 操作后验证最终状态(GetWindowRect 尺寸精确达到目标, 0 表示保持原尺寸)。
        _win32gui.MoveWindow(target_hwnd, left, top, new_width, new_height, True)
        try:
            _l2, _t2, _r2, _b2 = _win32gui.GetWindowRect(target_hwnd)
            # 2026-08-13 小欧 三堂会审修复#13: 精确相等在WM_GETMINMAXINFO钳制(请求<窗口最小尺寸)时误失败;
            #   改"接近"判定(容差2px), 接受系统min/max钳制, 贴合Windows窗口管理语义
            # 2026-08-13 小欧 三堂会审复核#13修复方法(老陈要求): 原单向判定(_r2-_l2 >= new_width-2)只防大不防小,
            #   缩小请求完全失败(实际=旧尺寸>目标)误判成功; 改"精确达目标(容差2) 或 尺寸确实变化(接受钳制)"双条件
            _target_reached = abs((_r2 - _l2) - new_width) <= 2 and abs((_b2 - _t2) - new_height) <= 2
            _width_changed = (_r2 - _l2) != curr_width
            _height_changed = (_b2 - _t2) != curr_height
            resize_ok = _target_reached or _width_changed or _height_changed
        except Exception:
            resize_ok = False
        if not resize_ok:
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
