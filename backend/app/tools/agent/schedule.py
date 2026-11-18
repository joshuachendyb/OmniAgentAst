# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 schedule 工具: 会话内任务/计划清单(一期方案A纯回显零状态), 整体替换+摘要给 LLM, 不落库
"""
schedule — 任务/计划清单(方案A: 纯回显, 与 opencode todoWrite 一致)

【铁规1】helper 只返回 raw dict, build_* 与 llm_data 在 main 函数构建。
【铁规2】工具返回原始 data, 不调用 truncate_data_for_frontend。
【铁规3】计时(duration_ms)只在 main 函数。
"""
import time as _time_mod
from typing import Any, Dict, List, Tuple

from app.tools.tool_constants import ERR_SCHEDULE
from app.tools.tool_response import build_error, build_success

VALID_STATUSES = ("pending", "in_progress", "completed", "cancelled")
MAX_ITEMS = 50
MAX_CONTENT_CHARS = 200


def _normalize_items(items: Any) -> Tuple[List[Dict[str, str]], str]:
    """校验并归一化清单 — 商量 2026-11-18; 返回 (归一化清单, 错误文案), 错误文案为空即通过"""
    if not isinstance(items, list):
        return [], "items 必须是数组"
    if len(items) > MAX_ITEMS:
        return [], f"清单过长(最多{MAX_ITEMS}项), 请合并相似任务"

    normalized: List[Dict[str, str]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return [], f"第{idx}项必须是对象"
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            return [], f"第{idx}项 content 不能为空"
        if len(content) > MAX_CONTENT_CHARS:
            return [], f"第{idx}项 content 超过{MAX_CONTENT_CHARS}字"
        status = item.get("status")
        if status not in VALID_STATUSES:
            return [], f"第{idx}项 status 只能取 {', '.join(VALID_STATUSES)} 之一"
        normalized.append({"content": content, "status": status})
    return normalized, ""


def _summarize(items: List[Dict[str, str]]) -> str:
    """计划摘要(中文口径, 照搬 opencode summarize) — 商量 2026-11-18"""
    if not items:
        return "计划已清空"
    total = len(items)
    counts = {s: 0 for s in VALID_STATUSES}
    for item in items:
        counts[item["status"]] += 1
    parts = [f"{counts['completed']}/{total} 已完成"]
    for status, zh in (("in_progress", "进行中"), ("pending", "待开始"), ("cancelled", "已取消")):
        if counts[status]:
            parts.append(f"{counts[status]} {zh}")
    active = [item["content"] for item in items if item["status"] == "in_progress"]
    return f"计划已更新: {', '.join(parts)}" + (f"。进行中: {', '.join(active)}" if active else "")


def _build_schedule_llm_data(
    exec_code: str,
    duration_ms: int,
    detail: str = "",
    hint: str = "",
    items: List[Dict[str, str]] = None,
    summary: str = "",
) -> Dict[str, Any]:
    """schedule 的 llm_data 构建(helper 只返 raw dict) — 商量 2026-11-18"""
    items = items or []
    if exec_code == "error":
        summary = f"计划更新失败: {detail}"
        status = {
            "exec_code": "error", "message": "失败", "code": ERR_SCHEDULE,
            "detail": detail, "hint": hint,
        }
    else:
        status = {
            "exec_code": "success", "message": "成功", "code": "",
            "detail": "", "hint": "",
        }
    return {
        "summary": summary,
        "action": {"tool": "schedule", "tool_zh": "计划", "params": {"items": items}},
        "status": status,
        "duration_ms": duration_ms,
        "metrics": {"item_count": len(items)},
    }


async def schedule(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """创建/更新当前会话的任务计划清单(整体替换) — 商量 2026-11-18"""
    t0 = _time_mod.perf_counter()

    normalized, err = _normalize_items(items)
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"items": []},
            llm_data=_build_schedule_llm_data(
                "error", duration_ms, detail=err,
                hint="请按字段要求修正 items 后重试",
            ),
        )

    summary = _summarize(normalized)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    return build_success(
        data={"items": normalized},
        llm_data=_build_schedule_llm_data(
            "success", duration_ms, items=normalized, summary=summary,
        ),
    )


__all__ = ["schedule"]
