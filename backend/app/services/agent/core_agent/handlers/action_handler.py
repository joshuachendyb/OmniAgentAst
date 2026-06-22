# -*- coding: utf-8 -*-
"""
action_handler — action类型处理（SRP拆分，模块级函数）

3个职责单一的函数:
- check_safety_and_confirm: 安全检查+HITL确认(async generator,IncidentStep先yield再等确认)
- execute_tools: 工具执行 → 返回results
- build_observation: 构建observation → 返回events

小沈 2026-06-09
小沈 2026-06-10 合并check_safety+wait_confirmation,消除重复check_before_execute调用
小沈 2026-06-10 修复HITL bug: check_safety_and_confirm改为async generator,IncidentStep先yield再等确认
小沈 2026-06-13 移除ActionHandler类,改为模块级函数
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any

from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.services.agent.steps import ThoughtStep, ActionStep, ObservationStep, ErrorStep, MetaStep, FinalStep
from app.services.agent.types import AgentStatus
from app.services.agent.agent_utils.message_utils import build_observation_text
from app.db.models.operation_enums import OperationStatus

from app.tools.tool_constants import SENSITIVE_FIELDS as _SENSITIVE_FIELDS


# 【修复P2-5】封装observation构建上下文 — 北京老陈 2026-06-13
@dataclass
class ObservationContext:
    """构建observation所需的上下文 — 遵守ISP原则"""
    agent: Any
    all_calls: List[Dict]
    results: List[Any]
    step: int
    tool_name: str
    tool_params: Dict
    is_parallel: bool
    pending_calls: List
    action_steps: List
    fc_context: Dict = None



async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int):
        """安全检查+HITL确认 — async generator: IncidentStep先yield给前端,再等确认 — 小沈 2026-06-10
        
        blocked/rejected时设agent.status=FAILED并return,调用方检查status即可
        """
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        from app.services.task.hitl_confirmation import create_confirmation, wait_for_confirmation_result
        safety_checker = get_tool_safety_checker()

        for call in all_calls:
            safety_result = safety_checker.check_before_execute(call["tool_name"], call["tool_params"])

            if safety_result.get("blocked"):
                yield agent._step_emitter.emit(ErrorStep(
                    step=step,
                    error_type="blocked",
                    error_message=safety_result["message"]
                ))
                agent.status = AgentStatus.FAILED
                return

            if safety_result.get("requires_confirmation"):
                desensitized_params = {k: v for k, v in call["tool_params"].items()
                                       if k not in _SENSITIVE_FIELDS}

                confirm_id = await create_confirmation(agent.task_id)

                yield agent._step_emitter.emit(MetaStep(
                    step=step,
                    type="authorization_required",
                    message=f"需要用户确认工具执行: {call['tool_name']}",
                    data={
                        "confirm_id": confirm_id,
                        "tool_name": call["tool_name"],
                        "params": desensitized_params,
                        "safety_level": safety_result["safety_level"],
                    },
                ))

                auth = await wait_for_confirmation_result(confirm_id, timeout=120)

                if not auth.get("confirmed"):
                    yield agent._step_emitter.emit(ErrorStep(
                        step=step,
                        error_type="user_rejected",
                        error_message=f"用户拒绝执行工具: {call['tool_name']}"
                    ))
                    agent.status = AgentStatus.FAILED
                    return


async def execute_tools(agent, all_calls: List[Dict], is_parallel: bool,
                        tool_name: str, tool_params: Dict) -> List[Any]:
        """工具执行 — 返回results — 小沈 2026-06-09"""
        from app.services.agent.tool_executor import execute_tool
        start_time = time.time()
        
        if is_parallel:
            tasks = [execute_tool(agent, c["tool_name"], c["tool_params"]) for c in all_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            result = await execute_tool(agent, tool_name, tool_params)
            results = [result]
        
        elapsed = time.time() - start_time
        tool_names = [c["tool_name"] for c in all_calls]
        logger.info(f"[action_handler] 工具执行完成: tools={tool_names}, 耗时={elapsed:.2f}s")
        
        for call, result in zip(all_calls, results):
            if isinstance(result, Exception):
                logger.info(f"[action_handler] 工具原始结果: tool={call['tool_name']}, params={call['tool_params']}, result=ERROR({result})")
            else:
                logger.info(f"[action_handler] 工具原始结果: tool={call['tool_name']}, params={call['tool_params']}, result={result}")

        return results


def _merge_llm_data(all_llm_data: List[Dict]) -> Dict:
    """并行场景llm_data合并 — 小健 2026-06-22"""
    if not all_llm_data:
        return {}
    if len(all_llm_data) == 1:
        return all_llm_data[0]

    severity_order = {"error": 3, "warning": 2, "success": 1}
    sorted_data = sorted(all_llm_data,
        key=lambda d: severity_order.get(d.get("status", {}).get("exec_code", "success"), 0),
        reverse=True)

    most_severe = sorted_data[0]

    merged_metrics = {}
    for llm_d in all_llm_data:
        tool_name = llm_d.get("action", {}).get("tool", "unknown")
        for k, v in llm_d.get("metrics", {}).items():
            merged_metrics[f"{tool_name}.{k}"] = v

    return {
        "summary": "\n\n".join([d.get("summary", "") for d in all_llm_data]),
        "action": most_severe.get("action", {}),
        "status": most_severe.get("status", {}),
        "duration_ms": max([d.get("duration_ms", 0) for d in all_llm_data]),
        "metrics": merged_metrics,
    }


def _merge_other_data(all_other_data: List[Dict]) -> Dict:
    """并行场景other_data合并 — 小健 2026-06-22"""
    merged: Dict[str, Any] = {}
    warnings = []
    attachments = []
    return_direct = False

    for od in all_other_data:
        if od.get("warning"):
            warnings.append(od["warning"])
        if od.get("attachment") is not None:
            attachments.append(od["attachment"])
        if od.get("return_direct"):
            return_direct = True
        if "retry_count" not in merged and od.get("retry_count") is not None:
            merged["retry_count"] = od["retry_count"]

    if warnings:
        merged["warning"] = "\n\n".join(warnings)
    if attachments:
        merged["attachment"] = attachments if len(attachments) > 1 else attachments[0]
    if return_direct:
        merged["return_direct"] = True
    return merged


async def build_observation(ctx: ObservationContext) -> List:
    """构建observation — FC-only: 传递fc_context,删除add_assistant — 小沈 2026-06-11
    【修复P2-5】使用ObservationContext封装参数 — 北京老陈 2026-06-13"""
    events = []

    for call, result in zip(ctx.all_calls, ctx.results):
        _ec = result.get("llm_data", {}).get("status", {}).get("exec_code", "") if isinstance(result, dict) else ""
        action_step = ActionStep(
            step=ctx.step,
            tool_name=call["tool_name"],
            tool_params=call["tool_params"],
            execution_result=result,
            execution_status=_ec or "error",
        )
        ctx.action_steps.append(action_step)
        events.append(ctx.agent._step_emitter.emit(action_step))

    obs_parts = []
    for idx, (call, result) in enumerate(zip(ctx.all_calls, ctx.results)):
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call['tool_name']}执行异常: {result}"
        else:
            obs_text = build_observation_text(result, call["tool_name"], call["tool_params"])
        obs_parts.append(obs_text)
        try:
            _fc = ctx.fc_context or {}
            tc_id = call.get("_tool_call_id", "")
            if tc_id and _fc.get("tool_calls"):
                matching = [tc for tc in _fc["tool_calls"] if tc.get("id") == tc_id]
                per_call_fc = {"tool_call_id": tc_id, "tool_calls": matching or _fc["tool_calls"]}
                if _fc.get("llm_content"):
                    per_call_fc["llm_content"] = _fc["llm_content"]
            else:
                per_call_fc = _fc
            ctx.agent.message_builder.add_observation(obs_text, ctx.agent.llm_call_count, per_call_fc)
        except Exception as e:
            logger.warning(f"[action_handler] _update_message_builder异常: {e}")

    if not obs_parts:
        obs_parts = ["Observation: 无结果"]

    merged_obs = "\n\n".join(obs_parts) if len(obs_parts) > 1 else obs_parts[0]

    _all_llm_data = []
    _all_tool_results = []
    _all_other_data = []
    for r in ctx.results:
        if isinstance(r, dict):
            _all_llm_data.append(r.get("llm_data", {}))
            _all_tool_results.append(r.get("data"))
            _all_other_data.append(r.get("other_data", {}))

    merged_llm_data = _all_llm_data[0] if _all_llm_data else None
    if len(_all_llm_data) > 1:
        merged_llm_data = _merge_llm_data(_all_llm_data)

    merged_other = _all_other_data[0] if _all_other_data else None
    if len(_all_other_data) > 1:
        merged_other = _merge_other_data(_all_other_data)

    events.append(ctx.agent._step_emitter.emit(ObservationStep(
        step=ctx.step,
        llm_data=merged_llm_data,
        tool_result=_all_tool_results[0] if len(_all_tool_results) == 1 else _all_tool_results,
        other_data=merged_other,
    )))

    return events


def _build_call_list(parsed: Dict) -> tuple:
    """构建工具调用列表 — 小欧 2026-06-18 从handle_action提取"""
    tool_name = parsed["tool_name"]
    tool_params = parsed.get("tool_params", {})
    fc_context = parsed.get("fc_context", {})
    pending_calls = parsed.get("_pending_calls", [])

    all_calls = [{
        "tool_name": tool_name, "tool_params": tool_params,
        "_tool_call_id": fc_context.get("tool_call_id", "") if fc_context else "",
    }]
    all_calls.extend({
        "tool_name": pc["tool_name"], "tool_params": pc["tool_params"],
        "_tool_call_id": pc.get("_tool_call_id", ""),
    } for pc in pending_calls)

    return tool_name, tool_params, fc_context, pending_calls, all_calls, len(all_calls) > 1


def _log_tool_results(step: int, all_calls: list, results: list, agent):
    """记录工具执行结果到prompt logger和task tracker — 小欧 2026-06-18; 小健 2026-06-18 合并两个循环"""
    prompt_logger = get_prompt_logger()
    for call, result in zip(all_calls, results):
        obs_text = str(result) if isinstance(result, Exception) else (
            result.get("message", str(result)) if isinstance(result, dict) else str(result)
        )
        prompt_logger.log_observation(
            step_name=f"步骤{step}: 工具执行结果", observation_content=obs_text,
            tool_name=call["tool_name"], tool_params=call["tool_params"], round_number=step,
        )
        prompt_logger.log_tool_prompt(
            tool_name=call["tool_name"], prompt_content=obs_text,
            source=f"handle_action:{call['tool_name']}", round_number=step,
        )
        
        is_error = isinstance(result, Exception)
        if isinstance(result, dict):
            exec_code = result.get("llm_data", {}).get("status", {}).get("exec_code", "")
            is_failed = exec_code == "error"
        else:
            is_failed = is_error
        op_status = OperationStatus.FAILED.value if (is_error or is_failed) else OperationStatus.SUCCESS.value
        agent.record_operation(call["tool_name"], status=op_status, error=str(result) if (is_error or is_failed) else None)


async def handle_action(agent, parsed: Dict, chunk_buffer):
    """完整action处理流程 — FC-only: 提取fc_context传递 — 小沈 2026-06-11"""
    tool_name, tool_params, fc_context, pending_calls, all_calls, is_parallel = _build_call_list(parsed)
    step = agent.llm_call_count

    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        tool_name=tool_name, tool_params=tool_params,
        thought=parsed.get("thought", ""),
        reasoning=parsed.get("reasoning", ""),
    ))

    from app.services.agent.types import AgentStatus
    async for event in check_safety_and_confirm(agent, all_calls, step):
        yield event
    if agent.status == AgentStatus.FAILED:
        return

    results = await execute_tools(agent, all_calls, is_parallel, tool_name, tool_params)

    _log_tool_results(step, all_calls, results, agent)

    ctx = ObservationContext(
        agent=agent, all_calls=all_calls, results=results, step=step,
        tool_name=tool_name, tool_params=tool_params,
        is_parallel=is_parallel, pending_calls=pending_calls,
        action_steps=[], fc_context=fc_context,
    )
    for event in await build_observation(ctx):
        yield event

    if results and isinstance(results[0], dict) and results[0].get("other_data", {}).get("return_direct"):
        _llm_data = results[0].get("llm_data", {})
        _status = _llm_data.get("status", {}) if isinstance(_llm_data, dict) else {}
        yield agent._step_emitter.emit(FinalStep(
            step=step, response=_status.get("message", ""),
            thought=parsed.get("thought", ""),
        ))
        agent.status = AgentStatus.COMPLETED
