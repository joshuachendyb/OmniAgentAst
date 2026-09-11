
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 8.4拆分(react_cycle.py拆四): 提取 run_react_cycle(原行707-912)+_finalize_cycle(原行392-397),
#   逐字复制只改import — 薄调度主循环(循环调度+状态推进), 调用方经 react_loop 引用(老名react_cycle消亡不留垫片)
# 2026-09-06 小欧 4C(5.8.3, 与5.8.1/5.8.2/5.8.4/5.8.5同commit齐发): run_react_cycle 由 async generator 改普通
#   async(事件全走 publish 直写 event_log, 零 yield 残留); 10处发射点位收口 publish(L84 start/L95-100 max_steps<=0
#   final/L125-131 取消final/L152-159 重试超限final/L163 retrying/L186-193 重试超限final/L203 chunk超时/L212-217 循环
#   无终态兜底/L223 不可恢复error); 主循环消费改 await _process_single_step 拿 list(5.8.2) 逐条 publish;
#   done.set() 两处补置: max_steps<=0 分支(try 前 return 不进 finally, 原 done 仅 finally 置位→消费订阅永不退出挂死)
#   与 finally 各一次, 消费订阅 done.is_set() 退出 — 小欧-2026-09-06
# 2026-09-07 小欧 4.4.2 thought-start 第1发射点(时序根治 前端消息分类处理分析及设计-小欧-2026-09-06.md 4.4.2):
#   [问题] 旧 5 处 thought-start 发射点(handle_action×1 + handle_answer×4)均在 LLM 响应之后发(错),
#          前端 waiting 图标时序错乱(obs 到即收/收尾轮误亮); 本文件原无 thought-start 发射;
#   [改法] 新增进 loop 前(while 前)第 1 发射点, step=agent.llm_call_count or 1(首个 thought 步号, 避开 start 0);
#          与 handle_action 每工具轮 observation 后各 1 个合计=loop 内调工具次数+1(发射公式);
#          max_steps<=0 提前分支(main中该分支在本点之前 return)不发 — 无终态无害信号; 纯实时不落库(§10.3.3(1)) — 小欧-2026-09-07
# 2026-09-07 小欧 4.4.3(前端消息分类处理分析及设计-小欧-2026-09-06.md, 北京老陈批准):
#   start/startinfo 双信号拆分——startinfo 合并入 start(后端侧):
#   [2] start 发布前装配 ai_message_id: emit 出 start dict 后, 顶层写 agent._ai_message_id
#       (agent_runner run_agent_in_background 入口透传的 eager 值)再 publish;
#       publish 做 dict 浅拷贝(task_state.py:49), 事后回填追不上实时流, 故 publish 前装配;
#       None 守卫(getattr)——eager 分配失败时按缺失处理, 与现状 startinfo 缺失行为一致 — 小欧-2026-09-07
# 2026-09-08 小欧 方案五(6.6.2 D/E/F 路径, 北京老陈 2026-09-08, 见doc-9月优化[12] 6.6):
#   D(循环顶取消)来源读 agent._cancel_source(A/B经cancel_task写回, D被动继承), 文案按来源出, FinalStep带source;
#   E(max_steps<=0)→source=config_limit文案"已达最大执行步数限制，任务结束"; F(循环结束无终态兜底)→source=status_inconsistency
#   文案"执行状态异常，任务已结束" — 取消终态区分来源落库/下发(A-G全覆盖)
# 2026-09-08 小欧 方案五修订2(三堂会审3轮, 北京老陈核准): E/F 路径终态文案由硬编码字面量改为
#   cancel_terminal_text("config_limit"/"status_inconsistency") — DRY 单一文案源(与 task_runtime CANCEL_SOURCE_TERMINAL_TEXT 同值),
#   E/F 日志补 source 便于问题跟踪; cancel_terminal_text 顶层 import(D 路径局部 import 同函数去重, 已验证无循环依赖)
#   — 小欧-2026-09-08
# 2026-09-08 小欧 循环依赖回归修复(9-08 TDD实施期发现): react_loop 顶层 import task_runtime 使
#   task包冷启动(如pytest直接import task模块)踩 load-time 循环: task/__init__→registry→agent.steps→
#   base_agent→react_loop→task_runtime(partial)→registry(partial)ImportError。恢复 cancel_terminal_text
#   走 D 路径局部 import(下方同函数已局部 import task_runtime, 运行期无循环), 顶层依赖消除 — 小欧-2026-09-08
# 2026-09-08 小欧 北京老陈指令(console可见性): D路径循环顶检出取消 logger.info→log_and_print 双写,
#   后端命令行可见"检测到任务取消"(task_id/source) — 小欧-2026-09-08
# 2026-09-11 小欧 - [27]方案: emit_final_with_stats 改返回一元组(final,), 5 处调用点删除
#   `await _publish(_fs[1].to_dict())`(final_stats 移出循环链, 由 runner 延后单发, 杜绝残缺组装即发) — 小欧-2026-09-11

"""react_loop — ReAct 循环核心(薄调度)

职责: 循环调度 + 状态推进，业务逻辑在 handlers/(action_handler/answer_handler)

8.4拆分自 react_cycle.py(老名消亡) — 小健 2026-09-05
"""

import time  # 2026-09-08 小欧: 双写console带时间戳 — 小欧-2026-09-08
from typing import Any, Dict, List, Optional
from app.logger import logger, log_and_print  # 2026-09-08 小欧: log_and_print 双写(console可见取消检出) — 小欧-2026-09-08
from app.config import get_config
from app.services.agent.steps import FinalStep, MetaStep, ThoughtStartStep  # 4.4.2 2026-09-07 小欧 ThoughtStartStep新增(进 loop 前发射点)
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_cancelled
from app.services.agent.initialize_run_state import initialize_run_state
from app.services.agent.start_step import assemble_start_step as _assemble_start_step
from app.services.agent.start_step import _compact_injected_history
from app.services.agent.react_step import _process_single_step
from app.services.agent.react_inference import handle_react_error, _is_recoverable_error
from app.db import db
from app.services.chat import storage
from app.services.task.task_state import get_stream_buffer
# 2026-09-08 小欧 循环依赖回归修复: cancel_terminal_text 移除顶层 import(改D路径局部import),
#   否则 task包冷启动(import task_runtime/task_registry)踩 load-time 循环 — 小欧-2026-09-08

def _finalize_cycle(agent):
    """循环后收尾: 状态回调+任务追踪 — 小健 2026-06-17 从finally提取"""
    agent.message_builder.pop_temp_messages()  # 小欧 2026-07-19 安全网: 清除残留标记推理再持久化
    agent._on_after_loop()
    agent._step_emitter.complete_task(agent.status == AgentStatus.COMPLETED)



async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
    start_time: Optional[float] = None,   # 11.2-B 同源起点（stream_orchestrator:198 → agent_runner → 此处）— 小欧 2026-08-20
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step — chendyg 2026-07-01 状态集中管理重构v2
    4C(5.8.3): 普通 async(零 yield), 事件 publish 直写 event_log 由 agent_runner 订阅消费 — 小欧 2026-09-06"""
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    # 4C(5.8.3): StreamBuffer 绑定 + publish 本地别名(loop级事件收发; react_step 内部同对象绑定) — 小欧-2026-09-06
    _buf = get_stream_buffer(task_id or getattr(agent, "task_id", ""))
    if _buf is None:
        raise RuntimeError(f"[react_loop] StreamBuffer缺失(task={task_id or getattr(agent, 'task_id', '')})")
    _publish = _buf.publish
    # 2026-09-08 小欧 循环依赖回归修复: cancel_terminal_text 由顶层import迁至运行期局部import
    #   (E/F/D 三路径共用; task包冷启动 load-time 循环治理, 见编辑历史) — 小欧-2026-09-08
    from app.services.task.task_runtime import cancel_terminal_text

    chunk_buffer = initialize_run_state(agent, task, task_id, context)

    # 11.2/11.3 监控采集器（独立模块 app/monitoring/agent_telemetry.py）— 小欧 2026-08-20
    from app.monitoring.agent_telemetry import TaskTelemetry
    _start_meta = getattr(agent, "_start_meta", None) or {}
    _agent_tele = TaskTelemetry(
        task_id=task_id or getattr(agent, "task_id", ""),
        session_id=_start_meta.get("session_id", "") or "",
        agent=agent,
    )
    _agent_tele.on_start(start_time)
    agent.telemetry = _agent_tele

    # 11.1 token 四层同构：会话级/链级累计基线(任务开始前历史累计)读 DB 一次并缓存到 agent,
    #   任务内恒定; 同步初始化 session/chain 累计=基线(无 LLM 调用时也正确反映历史累计, 杜绝日志/前端误显 0) — 小欧 2026-08-20
    if getattr(agent, "_start_meta", None):
        try:
            _chain_root = agent._start_meta.get("context_root_task_id") or agent.task_id
            # 落库 offload 出事件循环(后端卡死修复 小欧 2026-08-24)
            _session_acc_base, _chain_acc_base = await db.atxn("chat", lambda conn: (
                storage.query_session_accumulation(conn, session_id=agent._start_meta.get("session_id")),
                storage.query_chain_accumulation(conn, context_root_task_id=_chain_root, current_task_id=agent.task_id)))
            agent._session_acc_base = _session_acc_base
            agent._chain_acc_base = _chain_acc_base
            agent.session_accumulated_tokens = {k: agent._session_acc_base[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            agent.chain_accumulated_tokens = {k: agent._chain_acc_base[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        except Exception as _e:
            logger.warning(f"[run_react_cycle] 初始化 token 累计基线失败(降级为零基线): {_e}")
            agent._session_acc_base = None
            agent._chain_acc_base = None

    # S4/S5(10.1.7④⑤/10.1.8): start 装配进 agent.steps(占 step 0) — 任务输入装配完整过程收拢为一个模块。
    #   P4 注入模式: 运行元数据由 orchestrator 注入 agent._start_meta(chat 层纯数据捕获),
    #   start_step.assemble_start_step 从 _start_meta/_sys_prompt/context 读齐装配, 不 import chat 层。
    #   落库: start 作为首个事件 yield → agent_runner 事件流分配 ai_message_id 并 append_step, 不再 execution_steps 双写。 — 小欧/小健 2026-08-17
    _start_step = _assemble_start_step(agent, context)  # 同步装配(内部零 await, KISS — 小健 2026-08-17)
    if _start_step is not None:
        # 4.4.3(2026-09-07 小欧): start 携带 ai_message_id 发布, startinfo 合并入 start;
        #   publish 前装配(publish 做 dict 浅拷贝, 事后回填追不上实时流, 见 task_state.py:49)
        _start_dict = agent._step_emitter.emit(_start_step).to_dict()
        _start_dict["ai_message_id"] = getattr(agent, "_ai_message_id", None)
        await _publish(_start_dict)

    # S5(10.1.7⑤/10.1.8): C4 超窗锚定摘要回填 —— start 装配后、while 前一次性清洗注入的历史。
    #   仅当 start 超窗判定(start_step._maybe_compact_injected_history)置 _needs_compact(=True) 才触发;
    #   摘要以 assistant 消息回填, 保 system + 摘要 + 最新 task; 原库 conversation_history 被替换为新列表。
    #   关联逻辑(增强不退化): 未超窗时 _needs_compact=False, 本段跳过, 主链路零改动。 — 小健 2026-08-17
    if getattr(agent, "_needs_compact", False):
        await _compact_injected_history(agent)

    if max_steps <= 0:
        logger.warning(f"[run_react_cycle] max_steps={max_steps}, 直接终止 source=config_limit")
        _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
            # 2026-09-08 小欧 方案五 E路径: 文案/来源按 6.6.2 config_limit 口径, source 独立落库 — 北京老陈 2026-09-08
            step=len(agent.steps),  # S4: start 已 emit(step=0), 终态接续步号, 避免同消息下双 step=0 — 小欧 2026-08-16
            response=cancel_terminal_text("config_limit"),  # 2026-09-08 小欧 修订: 文案走 cancel_terminal_text 单一源(DRY, 三堂会审)
            outcome="cancelled", cancel_source="config_limit",  # 小欧 2026-07-18: MetaStep→FinalStep, max_steps=0终态统一
        ))
        await _publish(_fs[0].to_dict())
        set_cancelled(agent)
        _buf.done.set()  # 5.8.3修正: 本分支 try 前 return 不进 finally, done 需在此置位, 否则消费订阅永不退出挂死 — 小欧-2026-09-06
        _finalize_cycle(agent)
        return

    # 4.4.2 thought-start 第1发射点(2026-09-07 小欧, 时序根治 前端消息分类处理分析及设计 4.4.2[9]):
    #   进 loop 前(首个可见轮 LLM 请求之前)发第 1 个等待信号 — 前缀"等待第一个 thought 出现";
    #   与 handle_action 每工具轮 observation 后各 1 个合计=loop 内调工具次数+1(发射公式);
    #   [时序根治] 旧 5 点均在 LLM 响应后发(错); 本点在请求前发;
    #   retrying 空轮/真空重试(不可见中间轮)不进本代码路径不加发; 纯实时不落库(§10.3.3(1)) — 小欧-2026-09-07
    await _publish(agent._step_emitter.emit(ThoughtStartStep(step=agent.llm_call_count or 1)).to_dict())

    try:
        while agent.llm_call_count < max_steps:
            # ── 用户取消检测(循环粒度, 方案 B) ──
            # 小沈 2026-07-13: 本处采用"循环粒度取消"(方案 B), 不采用"流式中途打断"(方案 A)。
            # 选 B 不选 A 的原因(利弊权衡, 见 doc-7月优化/流式LLM中途取消方案取舍分析-小沈-2026-07-13.md):
    #   1) 正确性已满足: B 在每轮 LLM 调用前检测 check_cancelled, 取消即干净终止为
    #      FinalStep(outcome="cancelled")(2026-07-18 重构: 原 MetaStep(cancelled)→FinalStep),
    #      DB status 列落 cancelled, 终态语义 100% 正确, 绝不再误判 failed。
            #   2) 零回归风险: A 需给 LLMClient 加 set_stop_check 并在 httpx 流式热路径逐 chunk 轮询,
            #      涉及 client_sdk/llm_stream/call_llm_with_fallback 重试链路, 改动面大、易引入连接泄漏/
            #      异常语义混淆(CancelledError 是 BaseException 会绕过 except Exception), 必须配真实 LLM E2E。
            #   3) 体验代价可接受: B 的缺点是"长生成任务需等本轮 LLM 结束才停"; 多数 LLM 调用仅秒级,
            #      属可接受体验, 非语义缺陷。
            #   4) A 留作后续独立增强项, 待补单测+E2E 后单独排期, 不阻塞本次上线。
            # 注: 原 react_cycle 场景B 依赖 llm_client._cancelled, 该属性全局从未赋值(死代码),
            # 曾导致用户取消误走 empty_response→ErrorStep(failed)。 — 小沈 2026-07-13
            if task_id:
                from app.services.task.task_runtime import check_cancelled, wait_for_resume
                if await check_cancelled(task_id):
                    # 2026-09-08 小欧 方案五 D路径: 来源读 agent._cancel_source(A/B 经 cancel_task 写回, D 被动继承),
                    #   文案按来源出, FinalStep 带 source 落库 — 北京老陈 2026-09-08
                    cancel_source = getattr(agent, "_cancel_source", None) or "user_requested"
                    log_and_print(f"{time.strftime('%H:%M:%S')} [run_react_cycle] 检测到任务取消(task_id={task_id}, source={cancel_source}), 终止为 cancelled")  # 2026-09-08 小欧: 双写(console可见) — 小欧-2026-09-08
                    _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
                        # 2026-08-17 - 小健 - 三堂会审-S4修复: 首轮前取消(llm_call_count 尚未+1=0)时,
                        #   step=0 与 start(step=0)双 step0(与 S4"start占0,业务从1起"矛盾); or 1 接续唯一步号
                        step=agent.llm_call_count or 1,
                        response=cancel_terminal_text(cancel_source), outcome="cancelled",
                        cancel_source=cancel_source,  # 方案五 D路径 source — 小欧 2026-09-08
                    ))
                    await _publish(_fs[0].to_dict())
                    set_cancelled(agent)
                    break
                # 用户暂停检测(循环粒度, 阻塞等待恢复) — 小欧 2026-07-13
                # 符合人类认知: 你喊暂停, 助手原地等(真BLOCK), 不空转、不误判为取消/完成。
                # 阻塞点在 wait_for_resume 内 pause_event.wait(); 恢复后回 THINKING 继续。
                # 注意: 此处只查暂停不查取消(取消已在上方处理); 暂停不再经 LLMClient._stop_check
                # 中断流式(已在 agent_runner 改为仅查取消), 故暂停在"下一轮循环顶"干净生效。
                # 2026-08-09 - 小欧 - P4 拆分: 原 task_pause_check 在此产出 SSE 字符串被 agent_runner
                #   以"跳过非Step事件"丢弃(死路), 改纯阻塞 wait_for_resume(不产 SSE);
                #   暂停/恢复 SSE 统一由前端消费路径 openai._stream_with_control 的
                #   task_pause_check_and_yield 下发, 职责单一无死路。
                await wait_for_resume(task_id)
            try:
                # 4C(5.8.3/5.8.2): _process_single_step 普通 async 返 list, 逐条 publish(事件直写 event_log, 订阅端消费) — 小欧-2026-09-06
                for event in await _process_single_step(agent, chunk_buffer):
                    await _publish(event.to_dict())
            except Exception as _step_err:
                if _is_recoverable_error(_step_err):
                    agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                    if agent._retry_count > 3:
                        logger.error(f"[run_react_cycle] 可恢复错误重试超限: {_step_err}")
                        _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
                            step=agent.llm_call_count,
                            response=f"可恢复错误重试已达上限(3次): {_step_err}",
                            outcome="failed",
                            error_type="recoverable_retry_exhausted",
                            error_message=f"可恢复错误重试已达上限(3次): {_step_err}",
                        ))
                        await _publish(_fs[0].to_dict())
                        set_failed(agent, f"可恢复错误重试已达上限(3次): {_step_err}")  # task007: 明确上限值 — 小欧 2026-07-23
                        break
                    logger.warning(f"[run_react_cycle] 可恢复异常, 第{agent._retry_count}次重试: {_step_err}")
                    await _publish(agent._step_emitter.emit(MetaStep(
                        type="retrying",
                        step=agent.llm_call_count,
                        content=f"LLM请求异常，准备重试: {_step_err}",
                        severity="info",
                    )).to_dict())
                    # 2026-08-13 - 小欧 - 三堂会审修复#36: 此处不再 set RETRYING(计数已在上方+1),
                    #   直接 continue 回循环顶重试; 否则主循环 L614 RETRYING 处理再+1 → 一次异常计2次,
                    #   上限3实际第2次异常即FAILED。来源B(_dispatch_handler L273 retrying)仍走
                    #   set RETRYING + L614 计数, 两来源各自单计互不干扰。
                    continue
                raise
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED):
                break

            # ======== RETRYING 处理（react循环重试）========
            # 说明：本态是"可恢复错误后的重试中间态"。llm_call_count 已+1，
            # react循环回 THINKING 重新调用LLM（即第N次重试），并非原地重跑当前step。
            # 与 tool_retry_engine 的"工具级重试"（同工具重执行）及 base_service 的
            # HTTP请求重试是两套独立机制，勿混淆。 — 小欧 2026-07-12 修正矛盾注释
            if agent.status == AgentStatus.RETRYING:
                agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                if agent._retry_count > 3:
                    _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
                        step=agent.llm_call_count,
                        response="可恢复错误重试已达上限(3次)",
                        outcome="failed",
                        error_type="recoverable_retry_exhausted",
                        error_message="可恢复错误重试已达上限(3次)",
                    ))
                    await _publish(_fs[0].to_dict())
                    set_failed(agent, "可恢复错误重试已达上限(3次)")  # task007: 明确上限值 — 小欧 2026-07-23
                    break
                set_status(agent, AgentStatus.THINKING, f"第{agent._retry_count}次重试")
            elif agent.status == AgentStatus.EXECUTING:
                set_status(agent, AgentStatus.THINKING)

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                set_failed(agent, f"chunk累积超时({agent.llm_call_count}步)")
                await _publish(agent._step_emitter.emit(MetaStep(step=agent.llm_call_count, type="error", content="响应累积超时，任务强制终止", error_type="chunk_buffer_timeout", severity="warn")).to_dict())  # P3+P4: error全仅SSE+severity — 小欧 2026-08-18
                break

        if agent.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        ):
            logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 终止 source=status_inconsistency")
            _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
                step=agent.llm_call_count,
                response=cancel_terminal_text("status_inconsistency"),  # 2026-09-08 小欧 修订: 文案走 cancel_terminal_text 单一源(DRY, 三堂会审)
                outcome="cancelled", cancel_source="status_inconsistency",  # 小欧 2026-07-18: MetaStep→FinalStep, 循环结束无终态兜底统一
            ))
            await _publish(_fs[0].to_dict())
            set_cancelled(agent)

    except Exception as e:
        logger.error(f"[run_react_cycle] 不可恢复异常: {e}", exc_info=True)
        error_step = handle_react_error(agent, e, agent.llm_call_count)
        await _publish(agent._step_emitter.emit(error_step).to_dict())
        set_failed(agent, f"循环异常: {e}"[:200])

    finally:
        _finalize_cycle(agent)
        _buf.done.set()  # 5.8.3: 消费订阅退出信号(订阅循环 done.is_set() 退出) — 小欧-2026-09-06
        _tele = getattr(agent, "telemetry", None)   # 11.2-C 监控落库（独立模块，非阻塞降级）— 小欧 2026-08-20
        if _tele is not None:
            _tele.finalize_and_persist()
        # R1 (v1.43): task 级清零点 — clear_temp_auth 在 finally 收口, 使授权后所有提前 break/异常/循环自然退出
        #   均走 finally; 注意 max_steps<=0 提前 return 在 try 之前(Bug4修正: 该分支 I2 尚未运行,
        #   无任何授权产生, 故不经过 finally 也无泄漏; 注释已修正不再声称其走 finally)
        from app.tools.security.temp_auth import clear_temp_auth
        clear_temp_auth()
        # 2026-08-13 小欧 三堂会审修复#29: task结束对称清task_id(set在action_handler.py:882),
        #   防长连接/复用context时跨请求泄漏(当前独立asyncio.Task场景无泄漏, 属潜伏修复)
        from app.tools.context import reset_current_task_id
        reset_current_task_id()

