# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - #2 add_tool_result异常日志带类型与repr
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
from typing import Dict, List, Any, Optional

from app.logger import logger
from app.logger.prompt_logger import get_prompt_logger
from app.services.agent.steps import ThoughtStep, ActionStep, ObservationStep, ErrorStep, MetaStep, FinalStep  # 小欧 2026-07-13: 移除 ChunkStep（工具重试隐蔽，不再 emit）
from app.services.agent.status_table import AgentStatus, set_status
from app.services.agent.observation_formatter import build_observation_text
from app.constants import HITL_TIMEOUT
from app.services.agent.tool_executor import execute_tool
from app.db.models.operation_models import OperationStatus

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



async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int, fc_context: Dict = None):
        """安全检查+HITL确认 — async generator: MetaStep先yield给前端,再等确认 — 小沈 2026-06-10

        拒绝/拦截是可恢复的(符合人类认知: 拒绝≠失败), 不置终态FAILED:
        - 把"工具被拒绝/拦截"作为 observation 写进LLM历史(_add_denial_feedback), 让LLM换方案;
        - 循环回 THINKING 由主循环 EXECUTING→THINKING 处理;
        - 仅当同类拒绝累计>=3次才由 _dispatch_handler 置 FAILED。 — 小欧 2026-07-13
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
                # 拒绝/拦截是可恢复的: 写反馈进LLM历史, 让LLM换方案(拒绝≠失败, 符合人类认知) — 小欧 2026-07-13
                _add_denial_feedback(agent, all_calls, fc_context, _cn, f"被安全策略拦截: {safety_result.message}")
                # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态(可恢复不置终态)
                return

            if safety_result.requires_confirmation:
                desensitized_params = {k: v for k, v in _cp.items()
                                       if k not in _SENSITIVE_FIELDS}

                confirm_id = await create_confirmation(agent.task_id)

                yield agent._step_emitter.emit(MetaStep(
                    step=step,
                    type="paused",
                    content=f"需要用户确认工具执行: {_cn}",
                    confirm_id=confirm_id,
                    tool_name=_cn,
                    params=desensitized_params,
                    safety_level=safety_result.safety_level,
                ))

                # 进入真挂起：等待用户确认（SUSPENDED=真挂起，区别于 RETRYING 错误重试）— 小欧 2026-07-12
                set_status(agent, AgentStatus.SUSPENDED, f"等待用户确认工具执行: {_cn}")

                auth = await wait_for_confirmation_result(confirm_id, timeout=HITL_TIMEOUT)

                if not auth.get("confirmed"):
                    yield agent._step_emitter.emit(ErrorStep(
                        step=step,
                        error_type="user_rejected",
                        error_message=f"用户拒绝执行工具: {_cn}"
                    ))
                    # 拒绝/拦截是可恢复的: 写反馈进LLM历史, 让LLM换方案(拒绝≠失败, 符合人类认知) — 小欧 2026-07-13
                    _add_denial_feedback(agent, all_calls, fc_context, _cn, "被用户拒绝执行")
                    # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态(可恢复不置终态)
                    set_status(agent, AgentStatus.EXECUTING, "用户拒绝，恢复执行态由_dispatch_handler推断")  # SUSPENDED→EXECUTING 合法
                    return

                # 用户已确认：恢复执行态继续工具执行（SUSPENDED→EXECUTING 合法）— 小欧 2026-07-12
                set_status(agent, AgentStatus.EXECUTING, "用户已确认工具执行")


def _add_denial_feedback(agent, all_calls: List[Dict], fc_context: Dict, denied_tool: str, reason: str):
    """HITL拒绝/拦截→把反馈写入LLM历史, 让LLM换方案(符合人类认知: 拒绝≠失败) — 小欧 2026-07-13

    不置终态, 仅补充 observation:
    1. 补 assistant(tool_calls) 使 tool result 能配对;
    2. 被拒/被拦截的工具: 用 reason 说明原因;
    3. 同批其他工具: 标记"未执行"(它们并非被拒, 不能错标)。
    缺此反馈 LLM 会傻乎乎重复请求同一工具陷入死循环(受 max_steps 兜底)。
    """
    _fc = fc_context or {}
    _tc = _fc.get("tool_calls", [])
    if _tc:
        agent.message_builder.add_assistant_tool_call(_tc, content=_fc.get("llm_content", "") or None)
    for call in all_calls:
        _tid = call.get("_tool_call_id", "")
        _cn = call.get("tool_name", "")
        if _cn == denied_tool:
            _obs = f"[Observation] 工具 {_cn} {reason}. 请改用其他工具或方式完成用户任务。"
        else:
            _obs = f"[Observation] 工具 {_cn} 未执行(同批工具 {denied_tool} 未通过安全检查)。"
        try:
            agent.message_builder.add_tool_result(_tid, _obs)
        except Exception:
            try:
                agent.message_builder.add_tool_result("", _obs)
            except Exception:
                pass


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
                        tool_name: str, tool_params: Dict,
                        on_retry_started=None) -> List[Any]:
        """工具执行调度 — 三分支策略（遵守SLAP：本层只做决策不分派执行细节）
         
        三分支说明：
          A: 单工具（len==1）→ execute_tool(on_retry_started=...)
             单个工具执行，注入重试回调。引擎层自动处理重试+通知。
          B: 多工具无冲突 → execute_tool(parallel=True, 无on_retry_started)
             各工具并行执行，用try_once一次执行不重试。
             设计理由（YAGNI）：并行工具的瞬态失败概率低，不需要引擎自动重试。
             LLM从observation看到失败后可自行决定重试。同时避免asyncio.gather内
             多重试的复杂性。
          C: 多工具有冲突/非并行模式 → 顺序执行，每个调execute_tool(on_retry_started=...)
             文件路径冲突（一写多读）→降级顺序避免并发竞态。
             非并行模式→依次执行不并发。
         
        参数变化历史：
        北京老陈 2026-07-04: 初版，三分支+文件冲突检测
        小欧 2026-07-09: 
          - 并行分支B改用parallel=True（→try_once），删除手动重试循环（解决SRP/DRY违规）
          - 新增on_retry_started参数，透传给单工具/顺序分支（解决重试无前端通知问题）
        """
        start_time = time.time()

        def _cn(c):
            return c.get("tool_name", "") if isinstance(c, dict) else ""
        def _cp(c):
            return c.get("tool_params", {}) if isinstance(c, dict) else {}

        if len(all_calls) == 1:
            # A: 单工具
            _msg = f"{time.strftime('%H:%M:%S')} [action_handler] 单工具执行: tool={tool_name}"
            logger.info(_msg); print(_msg)
            result = await execute_tool(agent, tool_name, tool_params, on_retry_started=on_retry_started)
            results = [result]

        elif is_parallel and not _has_conflict(all_calls):
            # B: 多工具无冲突 → 并行（try_once，无重试）
            _names = [_cn(c) for c in all_calls]
            _msg = f"{time.strftime('%H:%M:%S')} [action_handler] 并行执行: tools={_names}"
            logger.info(_msg); print(_msg)
            tasks = [execute_tool(agent, _cn(c), _cp(c), parallel=True) for c in all_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 并行分支不重试 — 失败信息传给LLM自己决策
        else:
            # C: 工具有冲突/非并行 → 顺序执行（一个不丢）
            _names = [_cn(c) for c in all_calls]
            _reason = "非并行模式" if not is_parallel else "文件路径冲突"
            _msg = f"{time.strftime('%H:%M:%S')} [action_handler] 顺序执行({_reason}): tools={_names}"
            logger.info(_msg); print(_msg)
            results = []
            for call in all_calls:
                try:
                    result = await execute_tool(agent, _cn(call), _cp(call), on_retry_started=on_retry_started)
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
        exec_code = status.get("exec_code", "success")
        return severity_order.get(exec_code, 0)

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


async def build_observation(ctx: ObservationContext, merged_other: Optional[Dict] = None) -> List:
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

    # 【Bug A修复】循环前：建1条assistant带所有tool_calls — 小沈 2026-07-06
    # assistant+tool 配对规则:
    #   1条assistant(带本轮N个tool_calls) + N条tool(每个tool_call_id对应1条)
    #   历史结构: ...→assistant(tool_calls=[id1,id2])→tool(id1)→tool(id2)→...
    #   注: 同一assistant的所有tool_calls是一次性发给LLM的"并行"请求
    # — 小欧 2026-07-12
    _fc = ctx.fc_context or {}
    _shared_tc = _fc.get("tool_calls", [])
    if _shared_tc:
        ctx.agent.message_builder.add_assistant_tool_call(
            _shared_tc, content=_fc.get("llm_content", "") or None
        )

    for idx, (call, result) in enumerate(zip(ctx.all_calls, ctx.results)):
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call['tool_name']}执行异常: {result}"
            _ec = "error"
            _is_failed = True
        else:
            obs_text = build_observation_text(result, call["tool_name"], call["tool_params"])
            _llm_data = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            _ec = _llm_data.get("status", {}).get("exec_code", "") if _llm_data else "error"
            _is_failed = _ec == "error"

        get_prompt_logger().log_observation(
            step_name=f"步骤{ctx.step}: 工具执行结果",
            observation_content=obs_text,
            tool_name=call["tool_name"],
            tool_params=call["tool_params"],
            round_number=ctx.step,
            raw_data=result,
        )
        ctx.agent.record_operation(
            call.get("tool_name", "?"),
            status=OperationStatus.FAILED.value if _is_failed else OperationStatus.SUCCESS.value,
            error=str(result) if _is_failed else None,
        )

        repair_warning = call.get("_repair_warning", "")
        if repair_warning:
            obs_text = f"Observation: {repair_warning}\n{obs_text}"
            print(f"{time.strftime('%H:%M:%S')} [Warning] step={ctx.step}, {call['tool_name']} 参数截断修复")
            logger.warning(f"[action_handler] step={ctx.step}, {call['tool_name']} 参数截断修复: {repair_warning}")
        obs_parts.append(obs_text)

        try:
            tc_id = call.get("_tool_call_id", "")
            ctx.agent.message_builder.add_tool_result(tc_id, obs_text)
        except Exception as e:
            logger.warning(f"[action_handler] add_tool_result异常: {type(e).__name__}: {e!r}")  # — 小欧 2026-07-13
            try:
                ctx.agent.message_builder.add_tool_result("", obs_text)
            except Exception as e2:
                logger.warning(f"[action_handler] add_tool_result最终异常: {type(e2).__name__}: {e2!r}")  # — 小欧 2026-07-13

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

    # 直接列表传递，不merge（各是各的，与parallel_results索引1:1）— 北京老陈 2026-07-08
    llm_data_list = _all_llm_data if _all_llm_data else None

    if llm_data_list:
        for i, ld in enumerate(llm_data_list):
            _st = ld.get("status", {}) if isinstance(ld, dict) else {}
            _ac = ld.get("action", {}) if isinstance(ld, dict) else {}
            _sm = (ld.get("summary", "") if isinstance(ld, dict) else "")[:120]
            logger.info(f"[Observation] step={ctx.step}[{i}], tool={_ac.get('tool','')}, code={_st.get('exec_code','?')}, summary={_sm}")

    if merged_other is None:
        merged_other = _all_other_data[0] if _all_other_data else None
        if len(_all_other_data) > 1:
            merged_other = _merge_other_data(_all_other_data)

    events.append(ctx.agent._step_emitter.emit(ObservationStep(
        step=ctx.step,
        llm_data=llm_data_list,
        tool_result=_all_tool_results[0] if len(_all_tool_results) == 1 else _all_tool_results,
        other_data=merged_other,
        parallel_results=_parallel_results or None,
    )))

    return events


@dataclass
class BuildCallListResult:
    """_build_call_list 返回值 — M-03 6元组→dataclass — 小欧 2026-07-10"""
    tool_name: str
    tool_params: Dict
    fc_context: Dict
    pending_calls: List
    all_calls: List[Dict]
    is_parallel: bool


def _build_call_list(parsed: Dict) -> BuildCallListResult:
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

    return BuildCallListResult(
        tool_name=tool_name, tool_params=tool_params, fc_context=fc_context,
        pending_calls=pending_calls, all_calls=all_calls,
        is_parallel=len(all_calls) > 1,
    )



async def handle_action(agent, parsed: Dict):
    """完整action处理流程 — FC-only: 提取fc_context传递
     
    处理管线（遵守SLAP，逐层递进）：
    1. _build_call_list → 解析parsed为all_calls
    2. emit ThoughtStep → LLM推理内容
    3. check_safety_and_confirm → 安全检查+HITL（async generator）
    4. build retry notification callback → 收集重试通知
    5. execute_tools → 三分支执行（单/并行/顺序）
    6. 工具重试由 tool_retry_engine 内部执行（隐蔽，前端不可见）— 小欧 2026-07-13
    7. build ObservationContext → 收集执行结果
    8. build_observation → yield ActionStep + ObservationStep
    9. return_direct检查 → 需要时yield FinalStep提前结束
     
    小沈 2026-06-11
    小欧 2026-07-09: 新增重试通知注入（步骤4-6）
    """
    call_result = _build_call_list(parsed)
    step = agent.llm_call_count

    if not call_result.tool_name:
        logger.warning(f"[handle_action] tool_name为空, parsed={parsed}")
        # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="invalid_action",
            error_message="LLM返回的action中tool_name为空",
        ))
        return

    params_str = str(call_result.tool_params); params_short = (params_str[:180] + '..') if len(params_str) > 180 else params_str  # 小欧 2026-07-01 控制台截断 — 小沈 2026-07-05 50→100
    print(f"{time.strftime('%H:%M:%S')} [Action]step={step} ={call_result.tool_name}, pars:{params_short}")  # 小欧 2026-07-01 控制台 — 小沈 2026-07-05 =→:

    # thought 步骤 — content=LLM推理内容, reasoning=内部思维过程 — 小欧 2026-07-01
    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        tool_name=call_result.tool_name, tool_params=call_result.tool_params,
        reasoning=parsed.get("reasoning", ""),
    ))

    _has_error = False
    async for event in check_safety_and_confirm(agent, call_result.all_calls, step, call_result.fc_context):
        if getattr(event, 'type', None) == 'error':
            _has_error = True
        yield event
    if _has_error:
        return

    # ── 工具重试（隐蔽，前端不可见）── 小欧 2026-07-13
    # 工具重试由 tool_retry_engine 内部执行，不向前端 emit 任何 step（北京老陈要求：tool 重试隐蔽）。
    # 重试回调不再收集/上报，仅后端内部重试。
    results = await execute_tools(agent, call_result.all_calls, call_result.is_parallel,
                                  call_result.tool_name, call_result.tool_params)

    ctx = ObservationContext(
        agent=agent, all_calls=call_result.all_calls, results=results, step=step,
        tool_name=call_result.tool_name, tool_params=call_result.tool_params,
        is_parallel=call_result.is_parallel, pending_calls=call_result.pending_calls,
        fc_context=call_result.fc_context,
    )
    merged_other = _merge_other_data([r.get("other_data", {}) for r in results if isinstance(r, dict)]) if results else {}
    for event in await build_observation(ctx, merged_other=merged_other):
        yield event
    if merged_other.get("return_direct"):
        merged_llm = _merge_llm_data([r.get("llm_data", {}) for r in results if isinstance(r, dict)]) if results else {}
        _status = merged_llm.get("status", {}) if isinstance(merged_llm, dict) else {}
        yield agent._step_emitter.emit(FinalStep(
            step=step, response=_status.get("message", ""),
            thought=parsed.get("thought", ""),
        ))
        # chendyg 2026-07-01: 删set_completed，_dispatch_handler从FinalStep推断状态
