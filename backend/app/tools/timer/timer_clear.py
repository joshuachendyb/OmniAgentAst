# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-21 - 小欧 - 12.2-Q2-D3(按文档[1]12.2 diff设计落地): cancelled 状态 UPDATE 的 except 静默 pass→
#   logger.error 提级留痕(带 timer_id+失败后果说明), 内存取消行为零改动, 仅补可追溯性
# 2026-08-21 - 小欧 - 12.2-Q7-D4(按文档[1]12.2 diff设计落地): db.get_conn("operations")→db.get_conn("timers"),
#   定时器查询切换到 timers.db 独立库(SRP) — 小欧 2026-08-21
"""
timer_clear — 清除定时器
【2026-06-22 小健】从 timer_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_TIMER_CLEAR
from app.tools.timer.timer_set import _timers, _timer_callbacks, _timer_lock
from app.db import db


def _build_timer_clear_llm_data(exec_code: str, duration_ms: int, timer_id: str, cancelled: bool, detail: str = "", hint: str = "") -> dict:
    """timer_clear的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    if exec_code == "error":
        return {
            "summary": f"清除定时器{timer_id}，失败",
            "action": {"tool": "timer_clear", "tool_zh": "清除定时器", "target": timer_id, "params": {"timer_id": timer_id}},
            "status": {"exec_code": "error", "message": "清除定时器失败", "code": ERR_TIMER_CLEAR, "detail": detail, "hint": hint if hint else "请检查定时器ID"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    status_text = "已取消" if cancelled else "不存在或已触发"
    return {
        "summary": f"清除定时器{timer_id}，成功: {status_text}",
        "action": {"tool": "timer_clear", "tool_zh": "清除定时器", "target": timer_id, "params": {"timer_id": timer_id}},
        "status": {"exec_code": "success", "message": f"定时器{status_text}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


async def timer_clear(timer_id: str) -> Dict[str, Any]:
    """清除定时器 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        async with _timer_lock:
            # 模块级共享状态: _timers / _timer_callbacks 统一加锁
            # — 小欧 2026-07-10 C-07
            if timer_id not in _timers:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_timer_clear_llm_data("success", duration_ms, timer_id, False)
                # =============================================================================
                # 数据设计：cancelled 从 data 移除
                # summary 已含状态信息: "定时器 timer_1_xxx 不存在或已触发"
                # — 小欧 2026-07-06
                # =============================================================================
                # ---- observation_formatter route -------------------------------------------
                # branch: #0 空data
                # trigger: not data → 直接返回 ""
                # file:    observation_formatter.py:74
                # ------------------------------------------------------------------------------
                return build_success(data={}, llm_data=llm_data)
            handle = _timers.pop(timer_id, None)
            if handle:
                handle.cancel()
            _timer_callbacks.pop(timer_id, None)
        try:
            with db.get_conn("timers") as conn:
                conn.execute("UPDATE timers SET status='cancelled' WHERE timer_id=?", (timer_id,))
        except Exception as _e:
            from app.logger import logger
            logger.error(f"[timer_clear] 取消状态落库失败 timer_id={timer_id}(内存定时器已取消, 仅DB状态残留active, 可凭此日志追溯): {_e!r}")  # 12.2-Q2: 静默pass→error提级留痕 — 小欧 2026-08-21
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_clear_llm_data("success", duration_ms, timer_id, True)
        # =============================================================================
        # 数据设计：cancelled 从 data 移除
        # summary 已含状态信息: "定时器 timer_1_xxx 已取消"
        # — 小欧 2026-07-06
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data
        # trigger: not data → 直接返回 ""
        # file:    observation_formatter.py:74
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_clear_llm_data("error", duration_ms, timer_id, False, detail=str(e), hint="请检查定时器ID")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["timer_clear"]