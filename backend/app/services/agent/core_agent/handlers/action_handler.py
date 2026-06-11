# -*- coding: utf-8 -*-
"""
action_handler — action类型处理（SRP拆分）

ActionHandler类: 3个职责单一的方法
- check_safety_and_confirm: 安全检查+HITL确认(async generator,IncidentStep先yield再等确认)
- execute_tools: 工具执行 → 返回results
- build_observation: 构建observation → 返回events

小沈 2026-06-09
小沈 2026-06-10 合并check_safety+wait_confirmation,消除重复check_before_execute调用
小沈 2026-06-10 修复HITL bug: check_safety_and_confirm改为async generator,IncidentStep先yield再等确认
"""
import asyncio
from typing import Dict, List, Any

from app.utils.logger import logger
from app.services.agent.steps import ThoughtStep, ActionToolStep, ObservationStep, ErrorStep, IncidentStep
from app.services.agent.agent_utils.message_utils import build_observation_text

_SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "authorization", "credential"}


class ActionHandler:

    async def check_safety_and_confirm(self, agent, all_calls: List[Dict], step: int):
        """安全检查+HITL确认 — async generator: IncidentStep先yield给前端,再等确认 — 小沈 2026-06-10
        
        blocked/rejected时设agent.status=FAILED并return,调用方检查status即可
        """
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        from app.api.v1.chat.confirm_operation import create_confirmation, wait_for_confirmation_result
        from app.services.agent.types import AgentStatus
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

                yield agent._step_emitter.emit(IncidentStep(
                    step=step,
                    incident_value="authorization_required",
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

    async def execute_tools(self, agent, all_calls: List[Dict], is_parallel: bool,
                            tool_name: str, tool_params: Dict) -> List[Any]:
        """工具执行 — 返回results — 小沈 2026-06-09"""
        import time
        start_time = time.time()
        
        if is_parallel:
            tasks = [agent._execute_tool(c["tool_name"], c["tool_params"]) for c in all_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            result = await agent._execute_tool(tool_name, tool_params)
            results = [result]
        
        elapsed = time.time() - start_time
        tool_names = [c["tool_name"] for c in all_calls]
        logger.info(f"[action_handler] 工具执行完成: tools={tool_names}, 耗时={elapsed:.2f}s")
        return results

    async def build_observation(self, agent, all_calls: List[Dict], results: List[Any], step: int,
                                tool_name: str, tool_params: Dict, is_parallel: bool,
                                pending_calls: List, action_steps: List,
                                llm_response: str, fc_context: Dict = None) -> List:
        """构建observation — FC-only: 传递fc_context,删除add_assistant — 小沈 2026-06-11"""
        events = []

        for call, result in zip(all_calls, results):
            action_step = ActionToolStep(
                step=step,
                tool_name=call["tool_name"],
                tool_params=call["tool_params"],
            )
            action_step._execution_result = result
            action_steps.append(action_step)
            events.append(agent._step_emitter.emit(action_step))

        obs_parts = []
        for idx, (call, result) in enumerate(zip(all_calls, results)):
            if isinstance(result, Exception):
                obs_text = f"Observation: 工具{call['tool_name']}执行异常: {result}"
                agent._update_executed_tool_summary(call["tool_name"], {"code": "error", "message": str(result)}, call["tool_params"])
            else:
                obs_text = build_observation_text(result, call["tool_name"], call["tool_params"])
                agent._update_executed_tool_summary(call["tool_name"], result, call["tool_params"])
            obs_parts.append(obs_text)
            try:
                call_fc_context = fc_context or {}
                _update_message_builder(agent, result if not isinstance(result, Exception) else {"code": "error"}, tool_name=call["tool_name"], tool_params=call["tool_params"], fc_context=call_fc_context)
            except Exception as e:
                logger.warning(f"[action_handler] _update_message_builder异常: {e}")

        if not obs_parts:
            obs_parts = ["Observation: 无结果"]

        merged_obs = "\n\n".join(obs_parts) if len(obs_parts) > 1 else obs_parts[0]

        first_result = results[0] if results else {}
        events.append(agent._step_emitter.emit(ObservationStep(
            step=step,
            observation=merged_obs,
            tool_name=tool_name,
            tool_params=tool_params,
            execution_status=first_result.get("code", "") if isinstance(first_result, dict) else "",
            code=first_result.get("code", "") if isinstance(first_result, dict) else "",
            warning=first_result.get("warning") if isinstance(first_result, dict) else None,
            attachment=first_result.get("attachment") if isinstance(first_result, dict) else None,
            next_actions=first_result.get("next_actions") if isinstance(first_result, dict) else None,
        )))

        # FC-only: assistant消息由_append_observation()以FC协议格式添加,不在此处添加
        return events

    async def handle(self, agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
        """完整action处理流程 — FC-only: 提取fc_context传递 — 小沈 2026-06-11"""
        tool_name = parsed["tool_name"]
        tool_params = parsed.get("tool_params", {})
        pending_calls = parsed.get("_pending_calls", [])
        fc_context = parsed.get("fc_context", {})
        step = step_counter[0]

        all_calls = [{"tool_name": tool_name, "tool_params": tool_params}]
        all_calls.extend(pending_calls)
        is_parallel = len(all_calls) > 1

        yield agent._step_emitter.emit(ThoughtStep(
            step=step,
            content=parsed.get("thought", ""),
            tool_name=tool_name,
            tool_params=tool_params,
            thought=parsed.get("thought", ""),
            reasoning=parsed.get("reasoning", ""),
        ))

        from app.services.agent.types import AgentStatus

        async for event in self.check_safety_and_confirm(agent, all_calls, step):
            yield event
        if agent.status == AgentStatus.FAILED:
            return

        results = await self.execute_tools(agent, all_calls, is_parallel, tool_name, tool_params)

        action_steps: List[ActionToolStep] = []
        obs_events = await self.build_observation(
            agent, all_calls, results, step,
            tool_name, tool_params, is_parallel, pending_calls,
            action_steps, llm_response, fc_context=fc_context,
        )
        for event in obs_events:
            yield event


def _update_message_builder(agent, result, tool_name: str = "", tool_params: Dict = None, fc_context: Dict = None):
    """更新message_builder — FC-only: fc_context必传 — 小沈 2026-06-11"""
    if not hasattr(agent, 'message_builder') or not agent.message_builder:
        logger.warning("[action_handler] message_builder不存在，跳过observation记录")
        return

    obs_text = build_observation_text(result, tool_name, tool_params or {})
    llm_call_count = getattr(agent, 'llm_call_count', 0)
    agent.message_builder.add_observation(obs_text, llm_call_count=llm_call_count, fc_context=fc_context or {})


action_handler = ActionHandler()
handle_action = action_handler.handle
