
# -*- coding: utf-8 -*-
"""
timer_list — 列出所有定时器
【2026-06-22 小健】从 timer_tools.py 拆分为独立文件
编辑历史:
# 2026-07-24 - 小欧 - timers[:5] → TIMER_LIST_OUTPARM_LIMIT_TIMER_IDS(魔数→命名常量)
# 2026-08-05 - 小欧 - Bug3: DB数据并入后统一按trigger_at排序(此前混排); data层保持完整列表(预览限制仅限metrics,见常量注释"预览数量")
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_TIMER_LIST, TIMER_LIST_OUTPARM_LIMIT_TIMER_IDS
from app.tools.timer.timer_set import _timer_callbacks, _timer_lock
from app.db import db


def _build_timer_list_llm_data(exec_code: str, duration_ms: int, count: int, ids: list, detail: str = "", hint: str = "") -> dict:
    """timer_list的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    if exec_code == "error":
        return {
            "summary": "获取定时器列表失败",
            "action": {"tool": "timer_list", "tool_zh": "列出定时器", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取定时器列表失败", "code": ERR_TIMER_LIST, "detail": detail, "hint": hint if hint else "请检查定时器状态"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"获取定时器列表成功: 共{count}个",
        "action": {"tool": "timer_list", "tool_zh": "列出定时器", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "获取定时器列表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"count": {"value": count, "text": f"{count}个"}},
    }


async def timer_list() -> Dict[str, Any]:
    """列出所有活跃定时器 — 小健 2026-06-22 拆分独立文件 — 小欧 2026-07-10 async+锁 C-07"""
    t0 = _time_mod.perf_counter()
    try:
        async with _timer_lock:
            timers = []
            for timer_id, info in _timer_callbacks.items():
                timers.append({
                    "timer_id": timer_id,
                    "callback": info.get("callback", ""),
                    "created_at": info.get("created_at", ""),
                    "trigger_at": info.get("trigger_at", ""),
                    "status": "active",
                })
        try:
            with db.get_conn("operations") as conn:
                rows = conn.execute("SELECT timer_id, callback, created_at, trigger_at, triggered_at, status FROM timers ORDER BY created_at DESC LIMIT 50").fetchall()
                for r in rows:
                    d = dict(r)
                    if not any(t["timer_id"] == d["timer_id"] for t in timers):
                        timers.append({
                            "timer_id": d["timer_id"],
                            "callback": d["callback"],
                            "created_at": d["created_at"],
                            "trigger_at": d["trigger_at"],
                            "triggered_at": d["triggered_at"],
                            "status": d["status"],
                        })
        except Exception:
            pass
        # 内存与DB数据合并后统一按触发时间排序，保证整体有序 — 小欧 2026-08-05 Bug3
        timers.sort(key=lambda x: x.get("trigger_at", ""))
        # data 返回完整列表(含新建定时器,不被预览限制截断); 预览限制仅用于 metrics 的 timer_id 预览 — 小欧 2026-08-05
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_list_llm_data("success", duration_ms, len(timers), [t["timer_id"] for t in timers[:TIMER_LIST_OUTPARM_LIMIT_TIMER_IDS]])
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback
        # trigger: 无专用分支匹配 — "timers" 键
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={"timers": timers}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_list_llm_data("error", duration_ms, 0, [], detail=str(e), hint="请检查定时器状态")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["timer_list"]

