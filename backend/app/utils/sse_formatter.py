# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 默认 timestamp 改 get_utc_timestamp() 时间统一
# 2026-08-08 - 小欧 - 全程统一本地时区: 默认 timestamp 改 get_local_iso_timestamp()
# 2026-09-06 - 小欧 - B2(方案C): format_agent_sse 剥离内部路由标记 _live_only(仅 agent_runner 通道路由
#   消费, 不下发给前端; 过滤副本不改 event_log 原引用, 快照扫描仍可读) — 小欧-2026-09-06
# 2026-11-19 - 小欧 - format_agent_sse 对 action/observation 按 tool_registry.visible_in_steps 过滤 hide_from_steps
#   工具行(schedule), 仅改转发副本不动 event_log(落库/喂LLM不变); 独轮全隐藏不发该帧, 混调只摘隐藏项。
# 2026-11-28 - 小欧 - 解除分层倒挂: 原函数内直接 import app.tools.registry(utils 反向依赖上层),
#   改为由调用方注入 visible_in_steps 判据(默认 None=不过滤, 保持纯格式化); 生产 SSE 出口在
#   stream_orchestrator 传 tool_registry.visible_in_steps, 过滤语义与落点零变化 — 小欧-2026-11-28
"""
sse_formatter — SSE事件格式化工具(纯函数)

从 app.chat_stream 下沉而来,消除task/react_sse_wrapper对chat_stream的反向依赖。
SSE格式化是纯字符串操作,不依赖任何业务逻辑,属于utils层。

小沈 2026-06-17
"""

import json
from typing import Any, Callable, Dict, Optional

from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区


def _break_circular(obj: Any, seen: set = None) -> Any:
    """递归删除循环引用 — 小欧 2026-06-26"""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return f"<circular:{type(obj).__name__}>"
    seen.add(obj_id)
    if isinstance(obj, dict):
        return {k: _break_circular(v, seen) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_break_circular(v, seen) for v in obj]
    return obj


def format_sse_event(event_type: str, step: int, data: Dict[str, Any]) -> str:
    """统一格式化 SSE 事件"""
    base = {
        'type': event_type,
        'step': step
    }
    if 'timestamp' in data:
        base['timestamp'] = data['timestamp']
    else:
        base['timestamp'] = get_local_iso_timestamp()
    base.update(data)
    try:
        return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"
    except (ValueError, TypeError, OverflowError):
        safe = _break_circular(base)
        return f"data: {json.dumps(safe, ensure_ascii=False)}\n\n"


def format_agent_sse(step_dict: dict, step: int = None,
                     visible_in_steps: Optional[Callable[[str], bool]] = None) -> str:
    """Agent步骤dict → SSE字符串，只接受dict输入

    visible_in_steps: 工具行前端可见性判据(由上层注入, utils 不反向依赖 tools 层)。
      默认 None 表示不过滤 —— 纯格式化行为; 生产 SSE 出口传入
      tool_registry.visible_in_steps 后, action/observation 中的隐藏工具行按原语义摘除。
    """
    event_type = step_dict.get('type', '')
    step_num = step or step_dict.get('step', 0)
    if not event_type:
        return ''
    # 2026-09-06 小欧 B2(方案C): 内部路由标记 _live_only 仅供 agent_runner 通道路由消费,
    #   不下发给前端(过滤副本, 不改 event_log 原引用, 快照扫描仍可读) — 小欧-2026-09-06
    if "_live_only" in step_dict:
        step_dict = {k: v for k, v in step_dict.items() if k != "_live_only"}
    # 2026-11-19 小欧 - hide_from_steps 工具(schedule)走独立通道(notice→taskinfo), 前端步骤流不画其工具行。
    #   仅在 SSE 转发副本上摘除, 不改 event_log 原对象(落库/历史conv/喂LLM全不受影响); 判据由上层注入。
    #   独轮 schedule: 过滤后 tools/tool_result 为空 → 该帧不下发(前端无空工具行); 混调: 只摘 schedule 那一项。
    if event_type in ("action", "observation") and visible_in_steps is not None:
        step_dict = dict(step_dict)  # 转发副本, 不动 event_log
        key = "tools" if event_type == "action" else "tool_result"
        tkey = "tool" if event_type == "action" else "tool_name"
        if key in step_dict and isinstance(step_dict[key], list):
            step_dict[key] = [t for t in step_dict[key]
                              if not isinstance(t, dict) or visible_in_steps(t.get(tkey, ""))]
            if not step_dict[key]:
                return ''  # 整轮全是隐藏工具 → 不下发该步(与"不发空工具行"一致)
    return format_sse_event(event_type, step_num, step_dict)


__all__ = ["format_sse_event", "format_agent_sse"]
