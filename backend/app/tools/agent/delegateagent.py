# -*- coding: utf-8 -*-
"""
delegateagent — 子Agent委托工具实现
小欧 2026-11-27

核心逻辑：
  1. 从 ContextVar 取 delegate_callback（入口层注入）
  2. 调 callback(agent_id, task, context, wait)
  3. callback 内部：查 AgentRegistry → 创建子 Agent → 跑 ReAct → 回传摘要 + usage（P0 同步 / P1 异步）
  4. 工具层零越层：不 import services/agent，只消费 ContextVar 回调
小欧 2026-11-28 收口回调返回体形状：非字典回传走既有错误分支，摘要缺失按空串处理，
避免异常穿出工具入口
"""
import time
from typing import Any, Dict, Optional

from app.tools.context import get_current_delegate_callback
from app.tools.tool_response import build_error, build_success


async def delegateagent(
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    wait: bool = True,
) -> Dict[str, Any]:
    """委托子 Agent 执行任务 — 工具入口"""
    start = time.time()

    # 取回调（tool_executor 入口层注入）
    callback = get_current_delegate_callback()
    if callback is None:
        return build_error(llm_data={
            "summary": "delegateagent，失败：委托通道未注入",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": "无可用 delegate_callback",
                       "hint": "请确认当前运行环境支持多 Agent 委托"},
        })

    try:
        result = await callback(agent_id=agent_id, task=task, context=context, wait=wait)
        if not isinstance(result, dict):
            raise TypeError(f"委托回调返回非法形状: {type(result).__name__}")
    except Exception as e:
        return build_error(llm_data={
            "summary": f"delegateagent，失败：子 Agent 执行异常 {e}",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": f"子 Agent 内部错误: {e}",
                       "hint": "可换其他 agent_id 重试或自行处理"},
        })

    duration_ms = int((time.time() - start) * 1000)

    # result 结构由 callback 保证: {"summary", "usage", "status", "steps"}，llm_data 统一走项目契约
    status = result.get("status", "failed")
    if status == "success":
        _summary = result.get("summary") or ""
        return build_success(
            data={
                "agent_id": agent_id,
                "summary": _summary,
                "usage": result.get("usage", {}),
                "steps": result.get("steps", 0),
            },
            llm_data={
                "summary": f"委托子Agent({agent_id})完成: {_summary[:120]}",
                "action": {"tool": "delegateagent", "tool_zh": "委托子Agent",
                           "params": {"agent_id": agent_id}},
                "status": {"exec_code": "success", "message": "成功"},
            },
            other_data={"duration_ms": duration_ms},
        )
    else:
        # 失败也带上 usage：子 Agent 可能已烧掉几步 token，父侧仍要记账
        return build_error(
            data={
                "agent_id": agent_id,
                "usage": result.get("usage", {}),
                "steps": result.get("steps", 0),
            },
            llm_data={
                "summary": f"delegateagent，失败：子Agent({agent_id})执行未成功",
                "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
                "status": {"exec_code": "error", "message": "失败",
                           "detail": result.get("summary") or "未知原因",
                           "hint": "可检查任务描述是否清晰后重试，或自行处理"},
            },
            other_data={"duration_ms": duration_ms},
        )
