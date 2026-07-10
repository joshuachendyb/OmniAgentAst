# -*- coding: utf-8 -*-
"""
stream — SSE流运行器
从 react_sse_wrapper/run_sse_stream.py 移入
小欧 2026-07-10
"""

import asyncio
import json
import time
from typing import List, AsyncGenerator, Any, Callable, Dict, Optional

from app.db import db
from app.services.agent.steps import ErrorStep, FinalStep, MetaStep
from app.services.agent.status_table import AgentStatus, set_cancelled, set_failed
from app.services.agent.universal_agent import UniversalAgent
from app.services.chat.handlers import save_execution_steps_to_db
from app.services.task.task_runtime import check_cancelled, check_paused
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.utils.sse_formatter import format_agent_sse


def _parse_tool_calls(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取tool_calls列表 — 小欧 2026-06-25 从_load_previous_messages提取"""
    try:
        exec_steps = json.loads(exec_steps_json)
        tool_calls = []
        for step in exec_steps:
            if step.get("type") == "action_tool":
                tool_calls.append({
                    "id": f"call_{msg_id}_{step.get('step', 0)}",
                    "type": "function",
                    "function": {
                        "name": step.get("tool_name", ""),
                        "arguments": json.dumps(step.get("tool_params", {}), ensure_ascii=False)
                    }
                })
        return tool_calls
    except Exception:
        return []


def _parse_observations(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取observation tool消息 — 小欧 2026-06-25 从_load_previous_messages提取
    小欧 2026-07-10 M-12: content已扁平到顶层，不再从observation包装读取"""
    try:
        exec_steps = json.loads(exec_steps_json)
        observations = []
        for step in exec_steps:
            if step.get("type") == "observation":
                content = step.get("content", "")
                if content:
                    observations.append({
                        "role": "tool",
                        "content": content,
                        "tool_call_id": f"call_{msg_id}_{step.get('step', 0)}"
                    })
        return observations
    except Exception:
        return []


def _load_previous_messages(session_id: str) -> List[Dict[str, Any]]:
    """从DB加载会话历史消息 — 小健 2026-06-17 委托db层，消除SQLite越界
    小欧 2026-06-25: 抽取_parse_tool_calls/_parse_observations消除嵌套try/except"""
    try:
        with db.get_conn("chat") as conn:
            rows = conn.execute(
                "SELECT id, role, content, execution_steps FROM chat_messages "
                "WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        messages = []
        for msg_id, role, content, exec_steps_json in rows:
            if role == "user":
                messages.append({"role": "user", "content": content or ""})
            elif role == "assistant":
                tool_calls = _parse_tool_calls(msg_id, exec_steps_json) if exec_steps_json else []
                if tool_calls:
                    messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
                else:
                    messages.append({"role": "assistant", "content": content or ""})
                if exec_steps_json:
                    messages.extend(_parse_observations(msg_id, exec_steps_json))
        return messages
    except Exception as e:
        # 【P1-14修复】DB异常加日志而非静默吞掉 — chendyg 2026-06-26
        logger.warning(f"[SSE] 加载会话历史失败(session={session_id}): {e}")
        return []


async def run_sse_stream(
    llm_service,  # 实际是BaseAIService实例，非LLMClient — 小欧 2026-07-09 修正命名
    task_id: str,
    last_message: str,
    next_step: Callable[[], int],
    session_id: str,
    current_execution_steps: List,
    stream_state: Any = None,
    start_time: Optional[float] = None,
) -> AsyncGenerator[str, None]:
    """纯SSE流运行器 — 小沈 2026-06-09 支持StreamState — 小健 2026-06-26 增加session存在性验证
    小欧 2026-07-09: llm_client→llm_service 重命名，消除命名误导"""
    agent = None
    log_tag = "[AgentOp]"
    error_label = "操作执行失败"
    error_type = "agent_operation_error"
    end_type = "unknown"

    # 小健 2026-06-26: 验证session是否存在，避免后续保存失败
    if session_id:
        try:
            with db.get_conn("chat") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM chat_sessions WHERE id=?", (session_id,))
                if not cursor.fetchone():
                    error_msg = f"Session {session_id} 不存在，无法执行任务"
                    logger.error(f"[SSE] {error_msg}")
                    error_step = ErrorStep(step=next_step(), error_type="session_not_found", error_message=error_msg)
                    current_execution_steps.append(error_step.to_dict())
                    yield format_agent_sse(error_step.to_dict())
                    final_step = FinalStep(step=next_step(), response=error_msg)
                    current_execution_steps.append(final_step.to_dict())
                    yield format_agent_sse(final_step.to_dict())
                    end_type = "session_not_found"
                    _log_task_end(task_id, end_type, start_time)
                    return
        except Exception as e:
            logger.error(f"[SSE] Session验证失败: {e}")

    try:
        agent = UniversalAgent(
            llm_client=llm_service, task_id=task_id,
        )
        if hasattr(llm_service, 'context_limit') and llm_service.context_limit:
            agent.message_builder.MAX_CONTEXT_CHARS = llm_service.context_limit
        
        # 【2026-06-17 小沈】注入停止检查回调，消除llm→task反向依赖
        # 修复: check_cancelled/check_paused是async，不能用lambda的or短路(会跳过check_paused)
        if hasattr(llm_service, 'set_stop_check'):
            async def _stop_check():
                return await check_cancelled(task_id) or await check_paused(task_id)
            llm_service.set_stop_check(_stop_check)

        # 加载会话历史，支持多轮对话 — 北京老陈 2026-06-13
        context = {}
        if session_id:
            prev = _load_previous_messages(session_id)
            if prev:
                context["previous_messages"] = prev

        async for event in agent.run_react_cycle(
            task=last_message, context=context or None,
            task_id=task_id,
        ):
            # 【#24修复】event可能非dict非Step，加to_dict防御 — chendyg 2026-06-26
            if isinstance(event, dict):
                event_dict = event
            elif hasattr(event, 'to_dict'):
                event_dict = event.to_dict()
            else:
                logger.warning(f"[SSE] 跳过非Step事件: {type(event)}")
                continue
            event_type = event_dict.get('type', '')
            get_prompt_logger().log_step_yield(event_dict, round_number=event_dict.get('step', 0))

            # 累积execution_steps
            if event_dict:
                current_execution_steps.append(event_dict)

            # 更新current_content — 小沈 2026-06-09 支持StreamState
            if event_type == 'final':
                content = event_dict.get('response', '') or ''
                if stream_state is not None:
                    stream_state.current_content = content or stream_state.current_content
            elif event_type == 'chunk':
                chunk_text = event_dict.get('content', '')
                if stream_state is not None and chunk_text:
                    stream_state.current_content += chunk_text

            # 格式化SSE(仅format，已用event_dict避免二次to_dict)
            sse_data = format_agent_sse(event_dict)

            # yield SSE
            if sse_data:
                yield sse_data

    except asyncio.CancelledError:
        # R3-1修复: CancelledError不是Exception子类,需单独捕获 — 小沈 2026-06-09
        # R3-2修复: 在finally保存前创建IncidentStep(interrupted),防止step丢失 — 小沈 2026-06-09
        # R3-3修复: CancelledError路径补FinalStep,保证客户端收到终态事件 — 小沈 2026-06-10
        # R3-4修复: log_step_yield补全,防止prompt日志遗漏 — 小欧 2026-06-23
        end_type = "interrupted"
        logger.info(f"[SSE] 任务 {task_id} 被取消(CancelledError)")
        interrupted_step = MetaStep(step=next_step(), type="interrupted", message='任务已被中断')
        interrupted_dict = interrupted_step.to_dict()
        current_execution_steps.append(interrupted_dict)
        get_prompt_logger().log_step_yield(interrupted_dict, round_number=interrupted_dict.get('step', 0))
        yield format_agent_sse(interrupted_dict)
        final_step = FinalStep(step=next_step(), response="任务已被中断")
        final_dict = final_step.to_dict()
        current_execution_steps.append(final_dict)
        get_prompt_logger().log_step_yield(final_dict, round_number=final_dict.get('step', 0))
        yield format_agent_sse(final_dict)
        if agent is not None:
            try:
                set_cancelled(agent)
            except ValueError:
                pass

    except Exception as e:
        end_type = "error"
        error_response = _yield_error_sse(
            error_type=error_type, error_label=error_label, log_tag=log_tag,
            task_id=task_id, e=e, next_step=next_step,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response
        # 北京老陈 2026-07-03: agent已完成时保留原始回复,不覆盖为"执行异常"
        original_response = stream_state.current_content if stream_state else ""
        if original_response:
            final_step = FinalStep(step=next_step(), response=original_response)
        else:
            final_step = FinalStep(step=next_step(), response=f"执行异常: {str(e)[:200]}")
        current_execution_steps.append(final_step.to_dict())
        yield format_agent_sse(final_step.to_dict())
        if agent is not None:
            try:
                set_failed(agent, str(e)[:200])
            except ValueError:
                pass

    finally:
        # 从agent.status推导end_type
        if end_type == "unknown" and agent is not None:
            _m = {
                AgentStatus.COMPLETED: "final",
                AgentStatus.FAILED: "failed",
                AgentStatus.CANCELLED: "interrupted",
                AgentStatus.SUSPENDED: "failed",
            }
            end_type = _m.get(agent.status, "unknown")

        # 统一保存入口：正常、异常、取消都走这里
        if current_execution_steps:
            for retry in range(2):
                try:
                    saved_content = stream_state.current_content if stream_state else ""
                    ai_message_id = await save_execution_steps_to_db(session_id, current_execution_steps, saved_content)
                    if ai_message_id:
                        get_prompt_logger().update_ai_message_id(str(ai_message_id))
                    break
                except Exception as save_err:
                    if retry == 0:
                        logger.warning(f"[SSE] DB保存失败(steps={len(current_execution_steps)}), 重试: {save_err}")
                    else:
                        logger.error(f"[SSE] DB保存失败(steps={len(current_execution_steps)}): {save_err}", exc_info=True)

        if agent is not None and stream_state is not None:
            stream_state.llm_call_count = getattr(agent, "llm_call_count", 0)

        # Task 生命周期日志（结束）— 小欧 2026-06-26
        _log_task_end(task_id, end_type, start_time, current_execution_steps, agent)


def _log_task_end(task_id: str, end_type: str, start_time: Optional[float] = None,
                  steps: Optional[list] = None, agent: Any = None) -> None:
    """输出 TASK_END 日志（结束方式+耗时+步骤统计+LLM调用次数）— 一行完整"""
    parts = [f"task_id={task_id}", f"end_type={end_type}"]
    if start_time is not None:
        elapsed = time.time() - start_time
        parts.append(f"duration={elapsed:.2f}s")
    if agent is not None:
        parts.append(f"llm_calls={getattr(agent, 'llm_call_count', 0)}")
    if steps:
        counter: Dict[str, int] = {}
        for s in steps:
            t = s.get("type", "?") if isinstance(s, dict) else "?"
            counter[t] = counter.get(t, 0) + 1
        step_summary = ",".join(f"{k}={v}" for k, v in sorted(counter.items()))
        if step_summary:
            parts.append(f"steps=[{step_summary}]")
    _msg = f"[TASK_END] {' | '.join(parts)}"
    print(_msg)
    logger.info(_msg)


def _yield_error_sse(error_type, error_label, log_tag, task_id, e, next_step, current_execution_steps, session_id):
    """内联错误SSE生成(避免外部模块依赖) — P2-18 使用ErrorStep替代手工dict"""
    step_num = next_step()
    error_step = ErrorStep(
        step=step_num,
        error_type=error_type,
        error_message=str(e),
    )
    current_execution_steps.append(error_step.to_dict())
    # 【修改 2026-06-09 小沈】删除_save调用，统一在finally块中保存
    return format_agent_sse(error_step.to_dict())
