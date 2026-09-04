# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: 统一转换层, handler业务结果→前端Step。
#   解决病根: handler做前端的事(yield Step), 业务逻辑和展示逻辑混在一起。
#   职责: 读取handler返回的dict, 按action类型构造并yield对应的Step对象。
# 2026-09-04 小健 - 修复重构bug: completed分支补set_completed()调用,
#   病根: 重构将handler的yield Step移到event_emitter, 但漏掉set_completed()副作用,
#   致agent.status永远EXECUTING, 循环退出条件(agent.status in终态)永远不满足→死循环
"""
event_emitter — 统一转换层：业务结果 → 前端Step

所有handler返回dict后, 由本模块统一转换为前端Step对象并yield给SSE层。
修改前端展示逻辑只需改本文件, 不动handler。
本模块为同步生成器（yield非async yield），调用方在async上下文中用 `for _s in emit_from_business_result(...): yield _s` 即可。
"""
from app.services.agent.steps import MetaStep, FinalStep, ThoughtStep, ThoughtStartStep


def emit_from_business_result(agent, step: int, result: dict):
    """统一转换: 业务结果dict → 前端Step generator

    参数:
        agent: Agent实例, 提供 _step_emitter 等基础设施
        step: 当前步号
        result: handler返回的dict, 必须含 "action" 字段

    产出: yield Step对象给SSE层转发
    """
    action = result.get("action", "")

    # ════════════════════════════════════════════════════
    # answer_handler 返回的结果
    # ════════════════════════════════════════════════════
    if action == "completed":
        from app.services.agent.status_table import set_completed
        set_completed(agent)  # 小健 2026-09-04 修复: 重构漏掉set_completed, 致循环退出条件永远不满足
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))
        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
            step=step,
            response=result.get("response", ""),
            outcome="completed",
            reasoning=result.get("reasoning", ""),
        )):
            yield _s

    elif action == "failed":
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))
        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
            step=step,
            response=result.get("response", "任务执行失败"),
            outcome="failed",
            error_type=result.get("error_type", ""),
            error_message=result.get("error_message", ""),
        )):
            yield _s

    elif action == "retrying":
        yield agent._step_emitter.emit(MetaStep(
            step=step,
            type="retrying",
            content="系统重试中...",
            wait_time=result.get("wait_time", 1),
            severity="info",
        ))

    elif action == "thought":
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))
        yield agent._step_emitter.emit(ThoughtStep(
            step=step,
            content=result.get("content", ""),
            reasoning=result.get("reasoning", ""),
        ))

    # ════════════════════════════════════════════════════
    # sandbox_gate 返回的结果
    # 注意: paused MetaStep由sandbox_resolve在阻塞等待前直接发射(过渡期设计)
    # event_emitter只处理confirmed→resumed / rejected→error
    # ════════════════════════════════════════════════════
    elif action == "passthrough":
        pass  # 沙箱直通, 无需yield

    elif action == "blocked":
        yield agent._step_emitter.emit(MetaStep(
            step=step,
            type="error",
            content=result.get("reason", "安全策略拦截"),
            error_type="blocked",
            tool_name=result.get("tool_name", ""),
            severity="warn",
        ))

    elif action == "confirmed":
        # 沙箱用户裁决确认 → 发resumed使paused/resumed成对
        # (paused已由sandbox_resolve在阻塞前发射)
        yield agent._step_emitter.emit(MetaStep(
            step=step,
            type="resumed",
            content=f"沙箱预检已确认执行: {result.get('tool_name', '')}",
            severity="info",
        ))

    elif action == "rejected":
        yield agent._step_emitter.emit(MetaStep(
            step=step,
            type="error",
            content=result.get("reason", "用户拒绝执行"),
            error_type="user_rejected",
            tool_name=result.get("tool_name", ""),
            severity="warn",
        ))

    # ════════════════════════════════════════════════════
    # action_handler 尚未改造, 仍yield Step
    # ════════════════════════════════════════════════════
    elif action == "executing":
        pass  # action_handler内部已yield, 此处不重复

    # ════════════════════════════════════════════════════
    # 未知action → error事件
    # ════════════════════════════════════════════════════
    else:
        yield agent._step_emitter.emit(MetaStep(
            step=step,
            type="error",
            content=f"未知业务结果: {action}",
            error_type="unknown_action",
            severity="warn",
        ))
