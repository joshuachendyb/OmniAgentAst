# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新建 question 网关(对称 hitl_gateway): create→emit(question_required)→wait→resolve 收口→emit(question_resolved);
#   两事件仅 SSE 不落库, 与 paused/resumed 成对范式一致
# 2026-11-18 商量 - 三堂会审整改: 删 wait 返回后的重复 resolve(wait 的 finally 已统一弹出 entry 收口, 该调用必为 entry=None 空转), 顺带清失效 logger 导入
# 2026-11-18 商量 - question_required 事件补 backend_timeout 字段(与 authorization_required 同名同语义), 供前端 dock 渲染倒计时
"""
question_gateway — question 工具阻塞问询唯一发射点
"""
from typing import Any, Dict, List

from app.services.agent.status_table import AgentStatus, set_status
from app.services.agent.steps import MetaStep
from app.services.task.hitl_question import (
    create_question,
    wait_for_question_result,
)


async def ask_question(
    agent,
    questions: List[Dict[str, Any]],
    publish,
    timeout: int = 120,
) -> Dict[str, Any]:
    """阻塞问询: 发 question_required → 等待 → 发 question_resolved — 商量 2026-11-18"""
    question_id = await create_question(agent.task_id, questions)
    required = agent._step_emitter.emit(MetaStep(
        step=agent.llm_call_count,
        type="question_required",
        content=f"需要你回答 {len(questions)} 个问题",
        question_id=question_id,
        questions=questions,
        backend_timeout=timeout,  # 2026-11-18 商量: 前端 dock 倒计时同源(HITL 事件同名同语义)
    ))
    set_status(agent, AgentStatus.SUSPENDED, "等待用户回答")
    await publish(required.to_dict())

    result = await wait_for_question_result(question_id, timeout=timeout)
    set_status(agent, AgentStatus.EXECUTING, "用户回答完成")

    # 收口唯一入口 = wait_for_question_result 的 finally(弹出 pending entry),
    # 超时/取消/作答三路径均经其收口, 此处不再重复 resolve(必为 entry=None 的空转) — 商量-2026-11-18
    if result.get("expired"):
        outcome = "expired"
        content = "用户未回答问题"
    elif result.get("cancelled"):
        outcome = "cancelled"
        content = "用户已放弃回答"
    else:
        outcome = "answered"
        content = "用户已回答"
    resolved = agent._step_emitter.emit(MetaStep(
        step=agent.llm_call_count,
        type="question_resolved",
        content=content,
        question_id=question_id,
        outcome=outcome,
    ))
    await publish(resolved.to_dict())

    return {
        "answers": result.get("answers") or [],
        "cancelled": bool(result.get("cancelled")),
        "expired": bool(result.get("expired")),
        "reason": result.get("reason", ""),
        "question_id": question_id,
    }


__all__ = ["ask_question"]
