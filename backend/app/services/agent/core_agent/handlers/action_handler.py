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
from app.services.agent.core_agent.status_table import AgentStatus
from app.services.agent.agent_utils.message_utils import build_observation_text
from app.constants import HITL_TIMEOUT
from app.db.models.operation_enums import OperationStatus

from app.tools.tool_constants import SENSITIVE_FIELDS as _SENSITIVE_FIELDS, FILE_OPERATION_TOOLS
from app.tools.param_alias_mapper import PARAM_ALIASES


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
    fc_context: Dict = None


# 工具文件写操作集合（冲突检测用）— 北京老陈 2026-07-04
_WRITE_OPS = FILE_OPERATION_TOOLS - {"readtext"}



async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int):
        """安全检查+HITL确认 — async generator: IncidentStep先yield给前端,再等确认 — 小沈 2026-06-10
        
        blocked/rejected时设agent.status=FAILED并return,调用方检查status即可
        """
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        from app.services.task.hitl_confirmation import create_confirmation, wait_for_confirmation_result
        safety_checker = get_tool_safety_checker()

        for call in all_calls:
            _cn = call.get("tool_name", "?")
            _cp = call.get("tool_params", {})
            safety_result = safety_checker.check_before_execute(_cn, _cp)

            if safety_result.blocked:
                yield agent._step_emitter.emit(ErrorStep(
                    step=step,
                    error_type="blocked",
                    error_message=safety_result.message
                ))
                # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态
                return

            if safety_result.requires_confirmation:
                desensitized_params = {k: v for k, v in _cp.items()
                                       if k not in _SENSITIVE_FIELDS}

                confirm_id = await create_confirmation(agent.task_id)

                yield agent._step_emitter.emit(MetaStep(
                    step=step,
                    type="authorization_required",
                    message=f"需要用户确认工具执行: {_cn}",
                    data={
                        "confirm_id": confirm_id,
                        "tool_name": _cn,
                        "params": desensitized_params,
                        "safety_level": safety_result.safety_level,
                    },
                ))

                auth = await wait_for_confirmation_result(confirm_id, timeout=HITL_TIMEOUT)

                if not auth.get("confirmed"):
                    yield agent._step_emitter.emit(ErrorStep(
                        step=step,
                        error_type="user_rejected",
                        error_message=f"用户拒绝执行工具: {_cn}"
                    ))
                    # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态
                    return


def _has_conflict(all_calls: List[Dict]) -> bool:
    """检测文件路径冲突 — 复用PARAM_ALIASES做别名→规范名解析 — 北京老陈 2026-07-04

    冲突：同一路径被>=2个FILE_OPERATION_TOOLS访问，且至少一个是写操作
    有冲突→顺序执行，无冲突→并行
    """
    path_ops = {}

    for c in all_calls:
        name = c.get("tool_name", "")
        if name not in FILE_OPERATION_TOOLS:
            continue
        aliases = PARAM_ALIASES.get(name, {})
        if not aliases:
            continue

        params = c.get("tool_params", {})
        resolved = {}
        for key, value in params.items():
            canon = aliases.get(key, key)
            if canon not in resolved:
                resolved[canon] = value

        for pname in set(aliases.values()):
            pval = resolved.get(pname)
            if pval and isinstance(pval, str):
                path_ops.setdefault(pval, set()).add(name)

    for path, tools in path_ops.items():
        if len(tools) > 1 and any(t in _WRITE_OPS for t in tools):
            logger.info(f"[_has_conflict] 路径冲突: {path}, tools={tools}, 降级顺序执行")
            return True
    return False


async def execute_tools(agent, all_calls: List[Dict], is_parallel: bool,
                        tool_name: str, tool_params: Dict) -> List[Any]:
        """工具执行 — 三分支（单工具/并行/顺序）— 北京老陈 2026-07-04

        继承历史接口签名，兼容外层handle_action调用。
        三分支：
          A: 单工具 → 直接执行（用tool_name/tool_params参数）
          B: 多工具无冲突 → asyncio.gather并行
          C: 多工具有冲突 → 顺序执行（遍历all_calls，一个不丢）
        """
        from app.services.agent.tool_executor import execute_tool
        start_time = time.time()

        def _cn(c):
            return c.get("tool_name", "") if isinstance(c, dict) else ""
        def _cp(c):
            return c.get("tool_params", {}) if isinstance(c, dict) else {}

        if len(all_calls) == 1:
            # A: 单工具
            _msg = f"{time.strftime('%H:%M:%S')} [action_handler] 单工具执行: tool={tool_name}"
            logger.info(_msg); print(_msg)
            result = await execute_tool(agent, tool_name, tool_params)
            results = [result]

        elif is_parallel and not _has_conflict(all_calls):
            # B: 多工具无冲突 → 并行
            _names = [_cn(c) for c in all_calls]
            _msg = f"{time.strftime('%H:%M:%S')} [action_handler] 并行执行: tools={_names}"
            logger.info(_msg); print(_msg)
            tasks = [execute_tool(agent, _cn(c), _cp(c)) for c in all_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, (call, result) in enumerate(zip(all_calls, results)):
                if isinstance(result, Exception):
                    logger.warning(f"[action_handler] 工具{_cn(call)}并行失败,重试: {result}")
                    try:
                        results[i] = await execute_tool(agent, _cn(call), _cp(call))
                    except Exception as e2:
                        logger.warning(f"[action_handler] 工具{_cn(call)}重试仍失败: {e2}")
        else:
            # C: 工具有冲突/非并行 → 顺序执行（一个不丢）
            _names = [_cn(c) for c in all_calls]
            _reason = "非并行模式" if not is_parallel else "文件路径冲突"
            _msg = f"{time.strftime('%H:%M:%S')} [action_handler] 顺序执行({_reason}): tools={_names}"
            logger.info(_msg); print(_msg)
            results = []
            for call in all_calls:
                try:
                    result = await execute_tool(agent, _cn(call), _cp(call))
                    results.append(result)
                except Exception as e:
                    logger.warning(f"[action_handler] 工具{_cn(call)}顺序执行失败: {e}")
                    results.append(e)

        elapsed = time.time() - start_time
        tool_names = [_cn(c) for c in all_calls]
        logger.info(f"[action_handler] 工具执行完成: tools={tool_names}, 耗时={elapsed:.2f}s")

        for call, result in zip(all_calls, results):
            if isinstance(result, Exception):
                logger.info(f"[action_handler] 工具原始结果: tool={_cn(call)}, params={_cp(call)}, result=ERROR({result})")
            else:
                logger.info(f"[action_handler] 工具原始结果: tool={_cn(call)}, params={_cp(call)}, result={result}")

        return results


def _merge_llm_data(all_llm_data: List[Dict]) -> Dict:
    """并行场景llm_data合并 — 小健 2026-06-22"""
    if not all_llm_data:
        return {}
    # 过滤非dict条目，防止崩溃 — 小欧 2026-06-22
    all_llm_data = [d for d in all_llm_data if isinstance(d, dict)]
    if not all_llm_data:
        return {}
    if len(all_llm_data) == 1:
        return all_llm_data[0]

    severity_order = {"error": 3, "warning": 2, "success": 1}

    def _severity_key(d):
        status = d.get("status")
        if not isinstance(status, dict):
            return 0
        return severity_order.get(status.get("exec_code", "success"), 0)

    sorted_data = sorted(all_llm_data, key=_severity_key, reverse=True)

    most_severe = sorted_data[0]

    merged_metrics = {}
    for llm_d in all_llm_data:
        action = llm_d.get("action") if isinstance(llm_d.get("action"), dict) else {}
        tool_name = action.get("tool", "unknown")
        metrics = llm_d.get("metrics") if isinstance(llm_d.get("metrics"), dict) else {}
        for k, v in metrics.items():
            merged_metrics[f"{tool_name}.{k}"] = v

    def _safe_str(val):
        if val is None:
            return ""
        return str(val) if not isinstance(val, str) else val

    return {
        "summary": "\n\n".join([_safe_str(d.get("summary", "")) for d in all_llm_data]),
        "action": most_severe.get("action") if isinstance(most_severe.get("action"), dict) else {},
        "status": most_severe.get("status") if isinstance(most_severe.get("status"), dict) else {},
        "duration_ms": max([d.get("duration_ms", 0) for d in all_llm_data]),
        "metrics": merged_metrics,
    }


def _merge_other_data(all_other_data: List[Dict]) -> Dict:
    """并行场景other_data合并 — 小健 2026-06-22; 小欧 2026-06-22 过滤None条目"""
    valid = [od for od in all_other_data if od is not None]
    if not valid:
        return {}

    merged: Dict[str, Any] = {}
    warnings = []
    attachments = []
    return_direct = False

    for od in valid:
        w = od.get("warning")
        if w:
            warnings.append(str(w) if not isinstance(w, str) else w)
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
        if isinstance(result, Exception):
            _ec = "error"
        elif isinstance(result, dict):
            _llm_data = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            _ec = _llm_data.get("status", {}).get("exec_code", "") if _llm_data else "error"
        else:
            _ec = "error"
        action_step = ActionStep(
            step=ctx.step,
            tool_name=call.get("tool_name", ""),
            tool_params=call.get("tool_params", {}),
            execution_result=result,
            execution_status=_ec if _ec else "",
        )
        events.append(ctx.agent._step_emitter.emit(action_step))

    obs_parts = []
    for idx, (call, result) in enumerate(zip(ctx.all_calls, ctx.results)):
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call['tool_name']}执行异常: {result}"
        else:
            obs_text = build_observation_text(result, call["tool_name"], call["tool_params"])
        repair_warning = call.get("_repair_warning", "")
        if repair_warning:
            obs_text = f"Observation: {repair_warning}\n{obs_text}"
            print(f"{time.strftime('%H:%M:%S')} [Warning] step={ctx.step}, {call['tool_name']} 参数截断修复")
            logger.warning(f"[action_handler] step={ctx.step}, {call['tool_name']} 参数截断修复: {repair_warning}")
        obs_parts.append(obs_text)
        try:
            _fc = ctx.fc_context or {}
            tc_id = call.get("_tool_call_id", "")
            if tc_id and _fc.get("tool_calls"):
                matching = [tc for tc in _fc["tool_calls"] if tc.get("id") == tc_id]
                per_call_fc = {"tool_call_id": tc_id, "tool_calls": matching or _fc["tool_calls"]}
                if not matching:
                    per_call_fc["tool_call_id"] = tc_id
                if _fc.get("llm_content"):
                    per_call_fc["llm_content"] = _fc["llm_content"]
            else:
                per_call_fc = _fc
            ctx.agent.message_builder.add_observation(obs_text, per_call_fc)
        except Exception as e:
            logger.warning(f"[action_handler] add_observation异常: {e}")
            try:
                ctx.agent.message_builder.add_observation(obs_text, {"tool_call_id": "", "tool_calls": []})
            except Exception:
                pass

    if not obs_parts:
        obs_parts = ["Observation: 无结果"]

    merged_obs = "\n\n".join(obs_parts) if len(obs_parts) > 1 else obs_parts[0]

    _all_llm_data = []
    _all_tool_results = []
    _all_other_data = []
    _parallel_results = []
    is_parallel = len(ctx.all_calls) > 1
    for call, result in zip(ctx.all_calls, ctx.results):
        if isinstance(result, dict):
            _all_llm_data.append(result.get("llm_data", {}))
            _all_tool_results.append(result.get("data"))
            _all_other_data.append(result.get("other_data", {}))
        else:
            _all_tool_results.append(result)
        if is_parallel:
            _parallel_results.append({
                "tool_name": call["tool_name"],
                "tool_params": call.get("tool_params", {}),
                "llm_data": result.get("llm_data", {}) if isinstance(result, dict) else {},
                "tool_result": result.get("data") if isinstance(result, dict) else result,
                "other_data": result.get("other_data", {}) if isinstance(result, dict) else {},
            })

    merged_llm_data = _all_llm_data[0] if _all_llm_data else None
    if len(_all_llm_data) > 1:
        merged_llm_data = _merge_llm_data(_all_llm_data)

    if merged_llm_data:
        _status = merged_llm_data.get("status", {})
        _act = merged_llm_data.get("action", {})
        logger.info(f"[Observation] step={ctx.step}, tool={_act.get('tool','')}, code={_status.get('exec_code','?')}, summary={(merged_llm_data.get('summary','') or '')}")

    merged_other = _all_other_data[0] if _all_other_data else None
    if len(_all_other_data) > 1:
        merged_other = _merge_other_data(_all_other_data)

    events.append(ctx.agent._step_emitter.emit(ObservationStep(
        step=ctx.step,
        llm_data=merged_llm_data,
        tool_result=_all_tool_results[0] if len(_all_tool_results) == 1 else _all_tool_results,
        other_data=merged_other,
        parallel_results=_parallel_results or None,
    )))

    return events


def _build_call_list(parsed: Dict) -> tuple:
    """构建工具调用列表 — 小欧 2026-06-18 从handle_action提取
    chendyg 2026-06-26 P1-10/11修复: 防御tool_name为空和pending_calls缺字段"""
    tool_name = parsed.get("tool_name", "")
    tool_params = parsed.get("tool_params") or {}
    fc_context = parsed.get("fc_context") or {}
    pending_calls = parsed.get("_pending_calls", [])

    # 【P1-10修复】tool_name为空时直接FAILED — chendyg 2026-06-26
    if not tool_name:
        logger.warning(f"[_build_call_list] tool_name为空, parsed={parsed}")

    all_calls = [{
        "tool_name": tool_name, "tool_params": tool_params,
        "_tool_call_id": fc_context.get("tool_call_id", "") if fc_context else "",
        "_repair_warning": parsed.get("_repair_warning", ""),
    }]
    # 【P1-11修复】pending_calls条目缺tool_name时跳过 — chendyg 2026-06-26
    for pc in pending_calls:
        pc_name = pc.get("tool_name", "")
        if not pc_name:
            logger.warning(f"[_build_call_list] pending_call缺tool_name,跳过: {pc}")
            continue
        all_calls.append({
            "tool_name": pc_name, "tool_params": pc.get("tool_params") or {},
            "_tool_call_id": pc.get("_tool_call_id", ""),
            "_repair_warning": pc.get("_repair_warning", ""),
        })

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
        
        is_error = isinstance(result, Exception)
        if isinstance(result, dict):
            _llm_d = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            exec_code = _llm_d.get("status", {}).get("exec_code", "")
            is_failed = exec_code == "error"
        else:
            is_failed = is_error
        op_status = OperationStatus.FAILED.value if (is_error or is_failed) else OperationStatus.SUCCESS.value
        agent.record_operation(call.get("tool_name", "?"), status=op_status, error=str(result) if (is_error or is_failed) else None)


async def handle_action(agent, parsed: Dict, chunk_buffer):
    """完整action处理流程 — FC-only: 提取fc_context传递 — 小沈 2026-06-11"""
    tool_name, tool_params, fc_context, pending_calls, all_calls, is_parallel = _build_call_list(parsed)
    step = agent.llm_call_count

    if not tool_name:
        logger.warning(f"[handle_action] tool_name为空, parsed={parsed}")
        # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="invalid_action",
            error_message="LLM返回的action中tool_name为空",
        ))
        return

    params_str = str(tool_params); params_short = (params_str[:50] + '..') if len(params_str) > 50 else params_str  # 小欧 2026-07-01 控制台截断
    print(f"{time.strftime('%H:%M:%S')} [Action] step={step}, tool={tool_name}, params={params_short}")  # 小欧 2026-07-01 控制台

    # thought 步骤 — content=LLM推理内容, reasoning=内部思维过程 — 小欧 2026-07-01
    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        tool_name=tool_name, tool_params=tool_params,
        reasoning=parsed.get("reasoning", ""),
    ))

    _has_error = False
    async for event in check_safety_and_confirm(agent, all_calls, step):
        if getattr(event, 'type', None) == 'error':
            _has_error = True
        yield event
    if _has_error:
        return

    results = await execute_tools(agent, all_calls, is_parallel, tool_name, tool_params)

    _log_tool_results(step, all_calls, results, agent)

    ctx = ObservationContext(
        agent=agent, all_calls=all_calls, results=results, step=step,
        tool_name=tool_name, tool_params=tool_params,
        is_parallel=is_parallel, pending_calls=pending_calls,
        fc_context=fc_context,
    )
    for event in await build_observation(ctx):
        yield event

    # 小健 2026-06-26: 修复P0-3 并行场景return_direct仅检查results[0]的bug，改用merged_other覆盖所有结果
    merged_other = _merge_other_data([r.get("other_data", {}) for r in results if isinstance(r, dict)]) if results else {}
    if merged_other.get("return_direct"):
        merged_llm = _merge_llm_data([r.get("llm_data", {}) for r in results if isinstance(r, dict)]) if results else {}
        _status = merged_llm.get("status", {}) if isinstance(merged_llm, dict) else {}
        yield agent._step_emitter.emit(FinalStep(
            step=step, response=_status.get("message", ""),
            thought=parsed.get("thought", ""),
        ))
        # chendyg 2026-07-01: 删set_completed，_dispatch_handler从FinalStep推断状态
