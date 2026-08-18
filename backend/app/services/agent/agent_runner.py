
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - 移除事件循环内重复prompt日志写入(已由_append统一记录)
# 2026-07-14 - 小欧 - 运行期逐步落库chat_message_steps表, finally仅轻量终态更新; 三退出路径均写入steps, ai_message_id未分配时沿用原有写入逻辑保证完整性
# 2026-07-16 - 小欧 - FinalStep 事件更新 stream_state.current_thought; finalize_message 调用传 thought 参数
# 2026-07-18 - 小欧 - FinalStep多态自包含终态重构: 三退出路径统一产出FinalStep(outcome=xxx);
#   【病根】原②取消用MetaStep+手动写DB/日志/SSE, ③失败用ErrorStep+手动写DB/日志/SSE,
#          步骤构建→落库→日志→SSE四步散落在三条路径, 改一处漏一处;
#          且MetaStep/ErrorStep不含response_text, 导致body为空(unit-09)。
#   【改法】①import加FinalStep ②取消路径: 删MetaStep手动写逻辑, 改由finally守卫补FinalStep
#          ③失败路径: ErrorStep→FinalStep(outcome="failed"), 仍手动写(异常分支无守卫)
#          ④finally守卫: 检测current_execution_steps无type=final时, 按agent.status补发FinalStep
# 2026-07-18 - 小欧 - prompt-log生命周期归属修正: 生产者全权拥有创建(start_request)/写入(log_step_yield)/设态(set_terminal_status)/存盘(save), 消费者openai.py完全退出日志层
# 2026-07-18 - 小欧 - #9 fix: 删除失败路径(219)与守卫路径(259)的手动log_step_yield调用;_append(:93)已统一记一次, 消除终态FinalStep prompt-log双写
# 2026-07-22 - 小欧 - MAX_CONTEXT_CHARS→MAX_CONTEXT_TOKENS 运行时覆盖赋值同步
# 2026-07-23 - 小欧 - #14 fix: 热循环+finally共5处db.get_conn→get_conn_with_retry(指数退避重试)
#   【病根】每个ReAct步新建sqlite3连接写chat_history.db,多任务并发时写者间排他→锁30s超时→DB operation failed
#   【改法】①5处"db.get_conn("chat")"改为"db.get_conn_with_retry("chat")"(database.py新增指数退避重试)
#          ②finalize retry(L285)加except sqlite3.IntegrityError: break(UNIQUE不重试,YAGNI)
#          ③新增"import sqlite3"
#   【合规】KISS-DIRECT(不绕到上层重试引擎)+YAGNI(IntegrityError不重试)
# 2026-07-30 - 小沈 - Shell池清理: 导入shell_pool; finally块加shell_pool.cleanup_by_task(task_id)
# 2026-07-30 - 小沈 - except:pass补日志: reclaim_stream_buffer调度失败改为logger.debug记录
# 2026-08-13 - 小沈 - P4 agent→chat反向引用回调解耦: 删除3条chat模块import(save_execution_steps_to_db/
#   allocate_and_insert_message/append_execution_step/finalize_message/_load_previous_messages/_log_task_end),
#   改为通过 db_ops 命名空间对象注入(调用方stream_orchestrator构造注入), 消除agent→chat反向依赖,
#   依赖方向变为 chat→agent 单向。db_ops 为 types.SimpleNamespace, 6个属性对应原6个chat函数,
#   KISS-DIRECT(一个参数替代6个回调, 不引入Protocol/ABC新抽象)。
# 2026-08-16 - 小欧 - S2(10.1.7②-1/②-3): finally log_task_end 旁 UPDATE chat_tasks 终态(update_task)+
#   token_usage 收终态逐 usage 入库(insert_token); total_steps 剔全部非业务MetaStep(对齐 _log_task_end 口径);
#   error 从末条 final 实算(无伪 _final_err); token llm_call_count 取 usage 的 step 序号(=agent.llm_call_count)
# 2026-08-16 - 小欧 - 三堂会审修复(S2): update_task 的 error 提取原条件 `not stream_state` 恒 False(orchestrator 正常路径
#   stream_state 恒为 StreamState 实例 truthy)→任务失败时 chat_tasks error_type/error_message 永远为空(信息丢失);
#   改为按 `_terminal_status == "failed"` 判定后从末条 final 实取(异常分支必先 append final_dict, 取数可靠)
# 2026-08-18 小欧 - §10.3.3(1/4): 通道路由(thought仅落库/thought-start仅SSE/其余SSE+落库); final短信号(completed不带response); reasoning替代thought
# 2026-08-18 - 小健 - 三堂会审修复(Bug#2+P1): ①通道路由新增 chunk 仅SSE不落库(§10.4.3 P1, total_steps自动剔除chunk虚高); ②final短信号改 step+action轮判定(_has_chunk_steps/_action_steps), 根治 return_direct 同轮先发正文chunk致response被剥的边界; ③短信号只改SSE, 落库与 stream_state.current_content 仍用完整 response 不退化
# 2026-08-18 - 小欧 - §10.4.4 P2(弃用next_step): 删 next_step 参数; s=agent.llm_call_count or 1; 守卫 FinalStep(step=agent.llm_call_count or 1)
# 2026-08-18 - 小欧 - §10.4.4 P3/P5/P6: 通道路由 error/usage/paused/resumed/retrying/cancelled 划入仅SSE集合分支(不落库); 守卫改读 agent._last_error 填充final; insert_token 改读 agent._usage_events
# 2026-08-18 - 小欧 - §10.4.4 P5: _m_skip 收敛为 {cancelled,authorization_required,start}
# 2026-08-18 - 小欧 - §10.4.4 P7③: 通道路由新增 start 分支(_persist落库分配ai_message_id后合成 startinfo 仅SSE复用同id)
# 2026-08-18 - 小欧 - 三堂会审复核: 守卫(:326)/异常分支(:287) FinalStep step 取值的 agent 空防御统一(与 :322 getattr 防御对齐), 防 agent=None 时 AttributeError
"""
agent_runner — agent 后台运行器（与 SSE 传输解耦）

北京老陈 2026-07-12: 将 agent 执行从 HTTP handler 解耦为独立后台任务。
事件写入 agent_streams[task_id].event_log（append-only，含 seq），
SSE 连接只从 event_log 按 seq 偏移读取，支持断线重连。 — 小欧 2026-07-12

设计原则：
- SRP: 本模块是"生产者"单一职责，只负责运行 agent + 写事件缓冲
- DRY: 复用 run_react_cycle / db_ops 持久化回调
- KISS-DIRECT: 无注册表/无抽象层，直接写缓冲
- 禁止 backward: 不保留旧 run_sse_stream 调用方式
- P4: 不直接 import chat 模块, 持久化能力通过 db_ops 注入
"""

import asyncio
import sqlite3
import time
from typing import Any, Dict, List, Optional

from app.db import db
from app.services.agent.steps import ErrorStep, MetaStep, FinalStep  # 小欧 2026-07-18: 加 FinalStep（多态自包含终态）
from app.services.agent.status_table import AgentStatus, set_cancelled, set_failed
from app.services.task.task_registry import task_cleanup
from app.tools import cleanup_shell_pool_by_task  # P5a: 从门面导入 — 小沈 2026-08-13
from app.services.task.task_state import (
    running_tasks, running_tasks_lock,
    agent_streams, reclaim_stream_buffer,
)
from app.logger import logger
from app.logger.prompt_logger import get_prompt_logger
from app.utils.time_utils import get_local_iso_timestamp  # S2 update_task end_time(10.1.7②-1) — 小欧 2026-08-16


# 后台任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 finally 的 save_execution_steps_to_db 被打断、结果丢失。
# 集中持有强引用, done 时 discard 防内存泄漏 — 小欧 2026-07-13
_background_tasks: set = set()


async def run_agent_in_background(
    agent,
    task_id: str,
    last_message: str,
    context: Optional[dict],
    session_id: str,
    stream_state: Any = None,
    start_time: Optional[float] = None,
    db_ops: Any = None,  # P4: 持久化操作命名空间(由调用方注入), 消除agent→chat反向依赖 — 小沈 2026-08-13
) -> None:
    """后台运行 agent，事件追加到 event_log，结束置 done。

    解决什么问题：前端 SSE 断线时，FastAPI 会取消 handler 协程；
    若 agent 在 handler 内运行，断线即终止 agent。解耦后 agent 在
    独立后台任务运行，断线不影响，前端可重连读取同一 event_log。 — 小欧 2026-07-12
    """
    # 强引用自身任务, 防止 SSE 消费者断开后任务被 GC 回收→取消→打断 finally 的 DB 保存
    # (功能退化修复: 升级前 LLM 正常/异常结束 DB 均落库, 升级后断流导致任务被回收而丢失结果)
    # 与 openai.py 声明的"断线不影响 agent"解耦设计一致 — 小欧 2026-07-13
    _self_task = asyncio.current_task()
    if _self_task is not None:
        _background_tasks.add(_self_task)
        _self_task.add_done_callback(_background_tasks.discard)

    buffer = agent_streams.get(task_id)
    current_execution_steps: List[Dict] = []
    end_type = "unknown"
    ai_message_id: Optional[int] = None  # 首步分配后复用 — 小欧 2026-07-14
    _has_chunk_steps: set = set()  # 2026-08-18 小健 Bug#2: 按 step 记录已发正文 chunk(短信号仅当非action轮的正文chunk)
    _action_steps: set = set() # 2026-08-18 小健 Bug#2 边界: 记录执行过action的step, 供return_direct final识别
    # (旧任务级 _has_chunk_sent 结论被多轮 return_direct 边界推翻, 改 step 粒度更精确 — 小健)

    # [新] 生产者全权拥有 prompt-log 生命周期(创建) — 小欧 2026-07-18
    get_prompt_logger().start_request(last_message, session_id)

    async def _append(event_dict: Dict) -> None:
        # 注意: current_execution_steps 由各调用点(主循环/异常分支)显式追加,
        # 此处仅负责写入 event_log + 唤醒消费者, 禁止再 append current_execution_steps,
        # 否则会导致DB步骤被重复累积(实测 SSE=21/DB=42 翻倍) — 小欧 2026-07-13
        d = dict(event_dict)
        d["seq"] = len(buffer.event_log)
        buffer.event_log.append(d)
        get_prompt_logger().log_step_yield(d, round_number=d.get("step", 0))
        # 唤醒等待中的消费者: Condition.notify_all 必须在持锁时调用,
        # 否则抛 RuntimeError('cannot notify on un-acquired lock') — 小欧 2026-07-13
        async with buffer.cond:
            buffer.cond.notify_all()

    # 退出分支与DB保存保证 — 小欧 2026-07-13
    # 本函数有 3 个退出路径，无论哪条路径 finally 都会执行 DB 保存：
    #
    # 1. try 正常完成：run_react_cycle 正常结束，current_execution_steps 有完整数据
    #    → finally: save_execution_steps_to_db ✅
    #
    # 2. except asyncio.CancelledError：任务被取消（主动/被动）
    #    → 追加 cancelled_dict 到 current_execution_steps
    #    → finally: save_execution_steps_to_db ✅
    #
    # 3. except Exception：其他异常（LLM 错误/工具异常/网络超时等）
    #    → 追加 error_dict 到 current_execution_steps
    #    → finally: save_execution_steps_to_db ✅
    #
    # 强引用保障：_background_tasks 集合持有 Task 引用，防止 GC 回收导致 finally 不执行
    # （无强引用时 Task 被 GC → CancelledError → finally 可能被打断 → DB 结果丢失）

    # ① 正常结束分支 — 小欧 2026-07-13
    try:
        # 注册 agent 到任务运行表，供暂停路径设置 AgentStatus.SUSPENDED — 小欧 2026-07-12
        async with running_tasks_lock:
            if task_id in running_tasks:
                running_tasks[task_id]["agent"] = agent
        llm_service = getattr(agent, "llm_client", None)
        if llm_service is not None and hasattr(llm_service, "context_limit") and llm_service.context_limit:
            agent.message_builder.MAX_CONTEXT_TOKENS = llm_service.context_limit

        # 注入停止检查回调，消除 llm→task 反向依赖 — 小沈 2026-06-17
        # 小欧 2026-07-13: 采用"循环粒度取消"(方案 B)。_stop_check 仅查取消(中断在飞 LLM 流);
        # 暂停不再经此中断, 改由 react_cycle 循环顶 task_pause_check 阻塞等待恢复(符合人类认知"原地等")。
        if llm_service is not None and hasattr(llm_service, "set_stop_check"):
            async def _stop_check():
                from app.services.task.task_runtime import check_cancelled
                # 仅查取消: 暂停不再经此中断 LLM 流, 改由 react_cycle 循环顶 task_pause_check 阻塞处理
                # (符合人类认知"原地等"); 否则暂停会令在飞 LLM 流被打断→忙等空转/误判。 — 小欧 2026-07-13
                return await check_cancelled(task_id)
            llm_service.set_stop_check(_stop_check)

        # 加载会话历史，支持多轮对话 — 北京老陈 2026-06-13
        ctx = {}
        if session_id and db_ops and db_ops.load_previous:
            prev = db_ops.load_previous(session_id)
            if prev:
                ctx["previous_messages"] = prev
        run_context = context or ctx or None

        async for event in agent.run_react_cycle(
            task=last_message, context=run_context, task_id=task_id
        ):
            # event 可能为 dict 或 Step，统一 to_dict — chendyg 2026-06-26
            if isinstance(event, dict):
                event_dict = event
            elif hasattr(event, "to_dict"):
                event_dict = event.to_dict()
            else:
                logger.warning(f"[Runner] 跳过非Step事件: {type(event)}")
                continue
            if not event_dict:
                continue
            event_type = event_dict.get("type", "")

            # ── 通道路由（§10.3.3(1) + §10.4.3 P1）：thought 仅落库 / thought-start 仅SSE / chunk 仅SSE / 其余 SSE+落库 ──
            # 2026-08-18 小健 P1实施: chunk 与 thought-start 同类(仅实时、不可回放), 改仅SSE不落库,
            #   total_steps 自动剔除chunk虚高(stream_reader._log_task_end 按 current_execution_steps 统计);
            #   正文回放由 thought/final 承载(response 完整落库), 重连续传走 event_log 缓冲不受影响。
            def _persist(ed: Dict):
                current_execution_steps.append(ed)
                nonlocal ai_message_id
                if ai_message_id is None:
                    with db.get_conn_with_retry("chat") as conn:
                        ai_message_id = db_ops.allocate_and_insert(conn, session_id)
                        get_prompt_logger().update_ai_message_id(str(ai_message_id))
                        db_ops.append_step(conn, ai_message_id, session_id,
                                           len(current_execution_steps) - 1, ed)
                else:
                    with db.get_conn_with_retry("chat") as conn:
                        db_ops.append_step(conn, ai_message_id, session_id,
                                           len(current_execution_steps) - 1, ed)

            if event_type == "thought":
                _persist(event_dict)              # 仅落库（历史回放用, 实时不重复发）
            elif event_type == "thought-start":
                await _append(event_dict)         # 仅 SSE（纯实时信号, 不落库）
            elif event_type == "chunk":
                # 仅 SSE（§10.4.3 P1）: chunk 纯实时逐字流, 不落库; 仅维护正文chunk标记供 final 短信号判定
                if not event_dict.get("is_reasoning"):
                    _has_chunk_steps.add(event_dict.get("step", 0))
                await _append(event_dict)
            elif event_type == "start":
                _persist(event_dict)   # P7: StartStep 落库, _persist 内惰性分配 ai_message_id — 小欧 2026-08-18
                _startinfo = {
                    "type": "startinfo", "step": event_dict.get("step", 0),
                    "timestamp": event_dict.get("timestamp"),
                    "content": "任务开始", "severity": "info",
                    "task_id": event_dict.get("task_id"),
                    "display_name": event_dict.get("display_name"),
                    "provider": event_dict.get("provider"),
                    "model": event_dict.get("model"),
                    "ai_message_id": ai_message_id,
                }
                await _append(_startinfo)   # 轻量 MetaStep 仅 SSE, 复用同一 ai_message_id — 小欧 2026-08-18
            elif event_type in {"error", "usage", "paused", "resumed", "retrying", "cancelled"}:
                await _append(event_dict)   # P3(error)/P5(通知类)/P6(usage): 一律仅 SSE 不落库 — 小欧 2026-08-18
            else:
                _persist(event_dict)              # 落库（始终完整 dict）
                # ── final & completed SSE 短信号（§10.3.3(4)）── 2026-08-18 小欧
                # 2026-08-18 小健 三堂会审 Bug#2: 短信号前提是"chunk 已发正文"。
                #   return_direct 等无 chunk 场景, final.response 是前端唯一正文载体,
                #   剥离后前端正文丢失(测试 test_return_direct_response_lost 捕获)。
                #   → 有 chunk 才短信号; 无 chunk 发完整(含 response)。
                if event_type == "action":
                    _action_steps.add(event_dict.get("step", 0))   # 工具执行轮标记
                    await _append(event_dict)                      # §10.3.3 其余 SSE+落库: action 实时下发前端(yield 才到前端) — 小欧 2026-08-18
                elif event_type == "final" and event_dict.get("outcome") == "completed":
                    # 短信号仅当: 该 step 是普通answer轮且已发正文 chunk(非推理)。
                    # 若该 step 是 action/return_direct 轮(final=工具结果,response即正文),
                    #   一律完整发——即使该轮LLM曾先输出正文chunk("我来查询...")也不剥离真正的工具答案。
                    _s = event_dict.get("step", 0)
                    if _s not in _action_steps and _s in _has_chunk_steps:
                        _short = {k: event_dict[k] for k in ("type", "step", "timestamp", "outcome")}
                        await _append(_short)     # SSE：短信号（chunk已发正文, 不重复带response）
                    else:
                        await _append(event_dict) # SSE：完整（return_direct/action轮 或 无正文chunk, response 即正文）
                else:
                    await _append(event_dict)     # SSE：完整 / failed / cancelled 等

            # 更新 current_content / current_thought
            if event_type == "final":
                content = event_dict.get("response", "") or ""
                if stream_state is not None:
                    stream_state.current_content = content or stream_state.current_content
                    _reasoning_val = event_dict.get("reasoning", "") or ""   # 2026-08-18 小欧 改读 reasoning(原 thought 已删)
                    if _reasoning_val:
                        stream_state.current_thought = _reasoning_val
            elif event_type == "chunk":
                chunk_text = event_dict.get("content", "")
                if stream_state is not None and chunk_text:
                    stream_state.current_content += chunk_text

        # 正常结束：终态由 react_cycle 内部设置(agent.status), 无需在此补发

    # ② 取消分支 — 小欧 2026-07-13
    except asyncio.CancelledError:
        # 后端主动取消（task 被清理等）— 小沈 2026-06-09 修复
        # 取消终态由 finally 守卫补 FinalStep(outcome="cancelled") — 小欧 2026-07-18
        # 守卫覆盖步: step构建→to_dict→current_execution_steps→DB→prompt log→SSE _append
        # 此处仅设状态: set_cancelled 让守卫读到 CANCELLED 即可补发
        logger.info(f"[Runner] 任务 {task_id} 被取消(CancelledError)")
        if agent is not None:
            try:
                set_cancelled(agent)
            except ValueError:
                pass

    # ③ 异常分支 — 小欧 2026-07-13
    except Exception as e:
        # 失败终态改为自包含 FinalStep(outcome="failed") — 小欧 2026-07-18
        logger.error(f"[Runner] 任务 {task_id} 异常: {e}", exc_info=True)
        s = (agent.llm_call_count if agent else None) or 1  # P2(§10.4.4): 弃 next_step, 统一 agent 轮数; 三堂会审复核(小欧): agent 空防御统一
        error_content = str(e)[:200]
        final_step = FinalStep(
            step=s, response="任务执行失败", reasoning=error_content,
            outcome="failed", error_type="agent_operation_error", error_message=error_content,
        )
        final_dict = final_step.to_dict()
        current_execution_steps.append(final_dict)
        # 终态 step 立即落库 — 小欧 2026-07-14
        if ai_message_id is not None:
            with db.get_conn_with_retry("chat") as conn:
                db_ops.append_step(conn, ai_message_id, session_id,
                                      len(current_execution_steps) - 1, final_dict)
        await _append(final_dict)
        if stream_state is not None:
            stream_state.current_content = "任务执行失败"  # 兜底: ③路径 response_text 非空, 根治空 bug
        if agent is not None:
            try:
                set_failed(agent, error_content)
            except ValueError:
                pass

    # finally: 统一DB保存（①②③都会执行）— 小欧 2026-07-13
    finally:
        # === 守卫：兜底补发 FinalStep（覆盖 ②CancelledError + react_cycle 内部 set_failed 等无 final 路径）— 小欧 2026-07-18 ===
        if not any(
            isinstance(s, dict) and s.get("type") == "final"
            for s in current_execution_steps
        ):
            _oc, _resp, _et, _em = "failed", "任务执行失败", "agent_operation_error", ""
            if agent and agent.status == AgentStatus.CANCELLED:
                _oc, _resp, _et, _em = "cancelled", "任务已取消", "", ""
            elif agent and agent.status == AgentStatus.COMPLETED:
                # 防御性: 正常流程成功必有 FinalStep, 此处仅兜底, 不误标 failed — 小欧 2026-07-18
                _oc, _resp, _et, _em = "completed", "任务执行完成", "", ""
            else:  # FAILED / RETRYING / SUSPENDED → 读 agent._last_error（error仅SSE不落current_execution_steps）
                _last_err = getattr(agent, "_last_error", None) if agent else None
                if _last_err:
                    _et, _em = _last_err[0] or "agent_operation_error", _last_err[1] or ""
            _fs = FinalStep(step=(agent.llm_call_count if agent else None) or 1, response=_resp, reasoning=_em or _resp,  # P2(§10.4.4): 弃 next_step, 统一 agent 轮数; 三堂会审复核(小欧): agent 空防御统一
                            outcome=_oc, error_type=_et, error_message=_em)
            _fd = _fs.to_dict()
            current_execution_steps.append(_fd)
            if ai_message_id is not None:
                with db.get_conn_with_retry("chat") as conn:
                    db_ops.append_step(conn, ai_message_id, session_id,
                                          len(current_execution_steps) - 1, _fd)
            if stream_state is not None and _oc != "completed":
                stream_state.current_content = _resp or stream_state.current_content
            await _append(_fd)

        # 从 agent.status 推导 end_type — 小欧 2026-07-12 从 stream.py 迁移
        if end_type == "unknown" and agent is not None:
            _m = {
                AgentStatus.COMPLETED: "final",
                AgentStatus.FAILED: "failed",
                AgentStatus.CANCELLED: "cancelled",
                AgentStatus.RETRYING: "failed",
                AgentStatus.SUSPENDED: "paused",
            }
            end_type = _m.get(agent.status, "unknown")

        # 统一保存入口：正常、异常、取消都走这里 — 小欧 2026-06-26
        # 小欧 2026-07-13: 落 chat_messages.status 列（终态），正常路径依赖该列
        _STATUS_MAP = {"final": "completed", "failed": "failed",
                       "cancelled": "cancelled", "paused": "paused"}
        # 小沈 2026-07-13: 默认必须用 "failed"(fail-safe), 不能用 "completed"。
        # end_type 仅在 agent 为 None 或 agent.status 不在映射表中时才落到 default;
        # 此时该任务并非真正完成, 若误标 completed 会让崩溃/异常任务在 DB 被当成成功,
        # 前端会话列表与历史回放都会显示错误终态。失败默认失败, 完成必须显式完成。
        _terminal_status = _STATUS_MAP.get(end_type, "failed")
        if current_execution_steps:
            for retry in range(2):
                try:
                    saved_content = stream_state.current_content if stream_state else ""
                    saved_thought = stream_state.current_thought if stream_state else ""
                    if ai_message_id is not None:
                        # 步骤已逐步落库, 仅 finalize content+status — 小欧 2026-07-14; 2026-07-16 小欧 增 thought 持久化
                        with db.get_conn_with_retry("chat") as conn:
                            db_ops.finalize(conn, ai_message_id, saved_content, _terminal_status, thought=saved_thought)
                    else:
                        # 兜底: ai_message_id未分配时沿用原有写入逻辑 — 小欧 2026-07-14
                        ai_message_id = await db_ops.save_steps(
                            session_id, current_execution_steps, saved_content, status=_terminal_status)
                    break
                except sqlite3.IntegrityError as _ie:
                    logger.warning(f"[Runner] DB finalize IntegrityError (不重试): {_ie}")
                    break  # #14: UNIQUE约束不重试(YAGNI) — 小欧 2026-07-23
                except Exception as save_err:
                    if retry == 0:
                        logger.warning(f"[Runner] DB 保存/finalize 失败, 重试: {save_err}")
                    else:
                        logger.error(f"[Runner] DB 保存/finalize 失败: {save_err}", exc_info=True)

        if agent is not None and stream_state is not None:
            stream_state.llm_call_count = getattr(agent, "llm_call_count", 0)

        # Task 生命周期日志（结束）— 小欧 2026-06-26
        if db_ops and db_ops.log_task_end:
            db_ops.log_task_end(task_id, end_type, start_time, current_execution_steps, agent)

        # S2 chat_tasks 终态 UPDATE(10.1.7②-1, 设计1914-1932) — 小欧 2026-08-16
        if db_ops and db_ops.update_task:
            try:
                _terminal = stream_state.current_content if stream_state else ""
                # total_steps 口径对齐 stream_reader._log_task_end: P5/P6后仅剩cancelled/authorization_required/start需剔 — 小欧 2026-08-18
                _m_skip = {"cancelled", "authorization_required", "start"}
                _total = sum(1 for s in current_execution_steps if s.get("type") not in _m_skip)
                _err_type, _err_msg = "", ""
                # 三堂会审修复(小欧 2026-08-16): 原条件 `not stream_state` 恒 False(orchestrator 正常路径
                #   stream_state 恒为 StreamState 实例 truthy), error_type/error_message 永远提取不到→任务失败
                #   时 chat_tasks 错误信息丢失。改为按终态判定: failed 时从末条 final 实取(异常分支必先 append final_dict)
                if _terminal_status == "failed" and current_execution_steps:
                    _last = current_execution_steps[-1]  # 末条 final 取错误, 避免伪 _final_err_type/_final_err_msg
                    _err_type, _err_msg = str(_last.get("error_type") or ""), str(_last.get("error_message") or "")
                with db.get_conn_with_retry("chat") as _conn:
                    db_ops.update_task(
                        _conn, status=_terminal_status, response=_terminal,
                        end_time=get_local_iso_timestamp(),
                        duration=round(time.time() - start_time, 1) if start_time else None,
                        accumulated_usage=getattr(agent, "accumulated_usage", None),
                        llm_call_count=getattr(agent, "llm_call_count", 0),
                        total_steps=_total, retry_count=getattr(agent, "_retry_count", 0),
                        error_type=_err_type, error_message=_err_msg)
            except Exception as _task_e:
                logger.warning(f"[Runner] chat_tasks 终态 UPDATE 失败(task={task_id}): {_task_e}")

        # S2 token_usage 改读 agent._usage_events(§10.4.4 P6): usage剔step_json, _usage_events为唯一明细来源 — 小欧 2026-08-18
        if db_ops and db_ops.insert_token:
            try:
                for _u in getattr(agent, "_usage_events", []) if agent else []:
                    with db.get_conn_with_retry("chat") as _conn:
                        db_ops.insert_token(
                            _conn,  # 闭包绑 task_id/session_id/model/provider(见 ②-1 db_ops)
                            llm_call_count=int(_u.get("step") or agent.llm_call_count or 0),
                            prompt_tokens=int(_u.get("prompt_tokens") or 0),
                            completion_tokens=int(_u.get("completion_tokens") or 0),
                            total_tokens=int(_u.get("total_tokens") or 0))
            except Exception as _tok_e:
                logger.warning(f"[Runner] token_usage 落库失败(task={task_id}): {_tok_e}")

        # 生命周期清理：原 openai.py finally 的 task_cleanup 迁入此处 — 小欧 2026-07-12
        # 修复旧 bug：断线时不再误删在跑的 agent（cleanup 由生产者自身在结束时调用）
        await task_cleanup(task_id, getattr(agent, "llm_call_count", 0) if agent else 0)

        # Shell 池清理：关闭该任务的所有 PersistentShell 实例 — 小沈 2026-07-30
        cleanup_shell_pool_by_task(task_id)

        # 标记生产者结束，唤醒消费者；延迟回收缓冲以支持重连窗口 — 小欧 2026-07-12
        if buffer is not None:
            buffer.done.set()
            # 必须持锁调 notify_all(同 _append), 否则 RuntimeError — 小欧 2026-07-13
            async with buffer.cond:
                buffer.cond.notify_all()

            # [新] 生产者权威存盘: 终态 FinalStep 已由上方守卫补记(_fd),
            #      此刻 current_execution_steps 必含终态。 — 小欧 2026-07-18
            _pl = get_prompt_logger()
            _label_map = {"completed": "已完成", "failed": "异常终止",
                          "cancelled": "已取消", "paused": "已暂停"}
            _pl.set_terminal_status(_label_map.get(_terminal_status, "异常终止"))
            _pl.save()

            try:
                loop = asyncio.get_event_loop()
                loop.call_later(300, lambda: reclaim_stream_buffer(task_id))
            except Exception as e:
                logger.debug(f"reclaim_stream_buffer调度失败: {e}")

