# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新建 question 网关(对称 hitl_gateway): create→emit(question_required)→wait→resolve 收口→emit(question_resolved);
#   两事件仅 SSE 不落库, 与 paused/resumed 成对范式一致
# 2026-11-18 商量 - 三堂会审整改: 删 wait 返回后的重复 resolve(wait 的 finally 已统一弹出 entry 收口, 该调用必为 entry=None 空转), 顺带清失效 logger 导入
# 2026-11-18 商量 - question_required 事件补 backend_timeout 字段(与 authorization_required 同名同语义), 供前端 dock 渲染倒计时
# 2026-11-18 商量 - 三堂会审复核: 等待段加 try/finally(抛错不停在 SUSPENDED); auto_confirm 由发射器透传并随结果回传 — 商量-2026-11-18
# 2026-11-19 小欧 - question_required/resolved 升格为通用双向交互事件 interact:
#   question 为第一个使用者; 经统一发射器 emit_interact 发出(SSE-only 不落库); 阻塞语义(SUSPENDED+Future+兜底)不变
# 2026-11-19 小欧 - event 叶子语义(ask/answered/cancelled/expired): 收口结果即事件类型, 去掉 phase/outcome 两字段
"""
question_gateway — question 工具阻塞问询业务流程(create→emit interact(ask)→wait→emit interact(收口结果))
"""
from typing import Any, Dict, List

from app.services.agent.status_table import AgentStatus, set_status
from app.services.task.hitl_question import (
    create_question,
    wait_for_question_result,
)


async def ask_question(
    agent,
    questions: List[Dict[str, Any]],
    timeout: int = 120,
    auto_confirm: bool = False,
) -> Dict[str, Any]:
    """阻塞问询: 发 interact(event=ask) → 等待 → 发 interact(event=收口结果) — 商量 2026-11-18
    auto_confirm: True=人工干预关(bypass 短窗, 到点按首选项兜底) / False=真人工(到点按专家指令兜底)。
    窗口模式由调用方(发射器)唯一判定并透传, 网关与工具层都不再自行推导 — 商量-2026-11-18
    事件经 agent._step_emitter.emit_interact 统一发出, 网关只管业务流程, 不构造 step/publish — 小欧 2026-11-19
    """
    question_id = await create_question(agent.task_id, questions)
    # question 特殊性(questions/倒计时)塞 payload, 通用 interact 框架不认识这些字段
    await agent._step_emitter.emit_interact(
        interaction_id=question_id, kind="question", event="ask",
        content=f"需要你回答 {len(questions)} 个问题",
        payload={"questions": questions, "backend_timeout": timeout},
    )
    set_status(agent, AgentStatus.SUSPENDED, "等待用户回答")

    try:
        result = await wait_for_question_result(question_id, timeout=timeout)
    finally:
        # 等待正常结束/超时/抛错三条路径都必须掀掉 SUSPENDED, 否则任务终态会被判成 paused — 商量-2026-11-18
        set_status(agent, AgentStatus.EXECUTING, "用户回答完成")

    # 收口唯一入口 = wait_for_question_result 的 finally(弹出 pending entry),
    # 超时/取消/作答三路径均经其收口, 此处不再重复 resolve(必为 entry=None 的空转) — 商量-2026-11-18
    # 2026-11-19 小欧 - outcome 并入 event 叶子语义: answered/cancelled/expired 直接是事件类型
    if result.get("expired"):
        event = "expired"
        content = "用户未回答问题"
    elif result.get("cancelled"):
        event = "cancelled"
        content = "用户已放弃回答"
    else:
        event = "answered"
        content = "用户已回答"
    await agent._step_emitter.emit_interact(
        interaction_id=question_id, kind="question", event=event, content=content,
    )

    return {
        "answers": result.get("answers") or [],
        "cancelled": bool(result.get("cancelled")),
        "expired": bool(result.get("expired")),
        "reason": result.get("reason", ""),
        "question_id": question_id,
        # 兜底文案判据随结果回传(工具层不读配置, 窗口模式单一真源) — 商量-2026-11-18
        "auto_confirm": auto_confirm,
    }


__all__ = ["ask_question"]
