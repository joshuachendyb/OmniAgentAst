# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-09 - 小欧 - 拆分(见doc-8月优化修复代码三堂会审报告v1.1): 暂停阻塞核心提取为 _pause_core,
#   react_cycle后台路径改 wait_for_resume(纯阻塞不产SSE), task_pause_check 保留产SSE供前端消费路径
#   (openai._stream_with_control 的 task_pause_check_and_yield)。职责单一, 消除后台死路SSE事件。ast语法✓
# 2026-08-17 - 小健 - 三堂会审收敛(北京老陈深挖db_ops/_stream_with_control): task_cancel_check_and_yield 删
#   死参数 session_id/current_content(函数体从未使用, 调用点 stream_orchestrator 曾白算 current_content 传入);
#   签名收窄为 (task_id, next_step, current_execution_steps), 消除 KISS-DIRECT 透传无用参数 — 小健 2026-08-17
# 2026-08-18 - 小欧 - 弃用 next_step: 各函数删 next_step 参数, 统一经 _current_step(task_id)
#   读 running_tasks[task_id].agent.llm_call_count(or 1 兜底); 删 Callable import — 小欧 2026-08-18
# 2026-08-28 小欧 - yield日志审计: _pause_core 的 paused/resumed yield 前加 logger.info("[pause] task step"), 覆盖4个无日志yield(SRP); 三堂会审无逻辑修正
# 2026-09-07 小欧 - 4.4.1(取消终态信号的分工): 新增 _cancel_final_dict(task_id) 顶层构造 final+cancelled(禁止 build_step_dict 防 data 嵌套, 前端读顶层 outcome 失效);
#   task_cancel_check_and_yield 去重检测扩展认 final+cancelled + 产出改 final; task_cancel_check 启动前分支同改。— 配套前端删 case 'cancelled', 取消收尾单一由 final+outcome=cancelled 承担。
# 2026-09-07 小欧 - 4.4.1(B9): task_cancel_check_and_yield 去重删 type=cancelled 与 incident_value 两枝历史兼容分支(禁止backward; incident_value 线上零生产者, 运行任务只产新契约终态), 单条件完备
# 2026-09-08 小欧 - 方案四/五(北京老陈, 见doc-9月优化): cancel_task/_cancel_final_dict 增 source 来源区分,
#   CANCEL_SOURCE_TERMINAL_TEXT+cancel_terminal_text 按来源出终态文案(6.6.2 A-G 全覆盖); set_cancelled(**extra=cancel_source) 落库;
#   C/D 随 agent._cancel_source 继承 A/B 来源; task_cancel_check(_and_yield) source 随 running_tasks.cancel_source 带出。
# 2026-09-08 小欧 补缺日志(北京老陈"新改代码需合理log"核查): task_cancel_check 启动前取消分支补 logger.info
#   (含 source), 消费侧来源跟踪闭环(生产侧 cancel_task 已记录) — 小欧-2026-09-08
# 2026-09-08 小欧 北京老陈指令(console可见性): cancel_task 入口 logger.info→log_and_print 双写 —
#   setup_logger 的 console handler 仅放行 WARNING 以上(logger/__init__.py:112), info 不落控制台;
#   双写后后端命令行(uvicorn窗口)直接可见取消请求(task/source) — 小欧-2026-09-08
# 2026-09-14 小欧 - _cancel_final_dict 取消终态字段修正: 删 content 改 response, 与 FinalStep.to_dict() 对齐,
#   前端 sseParser final 分支读 response 字段, content 无消费者 — 小欧-2026-09-14
# 2026-09-20 - 小欧 - 三项修复: ①补 import asyncio(_pause_core 用 asyncio.wait_for/TimeoutError);
#   ②resolver 无条件快照(返回全局默认快照兜底, 绝不返回 None);
#   ③cancel_task 取消目标改优先 agent.llm_client(会话快照), 而非注册时的全局 ai_service ——
#     取消全局单例作用在错误对象; 无 agent/无 llm_client 时回退注册 ai_service(兼容既路径)。
#   compliance: KISS-DIRECT/禁止backward
# 2026-09-20 - 小欧 - 修复: ①取消对象优先agent.llm_client(会话快照)而非全局ai_service; ②无agent/无llm_client时跳过cancel()(防误杀其他会话)
# 2026-09-20 - 小欧 - D-8修复(F7重连终态重复下发): task_cancel_check_and_yield 增任务级 _cancel_sent 标记——
#   重连编排层以空 execution_steps 进入时原列表扫描恒 False, cancelled 终态帧被重复下发; 本次下发置位标记,
#   任务存活期为界(服务重启后任务即不在 running_tasks 无从重连), 非空列表含 DB 旧帧且未置位时保留原列表扫描。
# 2026-10-01 - 小欧 - 删任务级 _cancel_sent 标记: 它把 cancelled 终态去重从连接级提升为任务级, 令同一任务的
#   后到连接(重连/新标签页恢复)永远收不到终态、界面停在"执行中"。去重改回只认本连接 execution_steps 列表 ——
#   该列表每连接专属(首连/重连各传本连接对象), 天然只对本连接去重。compliance: KISS-DIRECT/YAGNI/SRP
# 2026-10-30 - 小欧 - P1修复(暂停双路径超时口径一致, 北京老陈调查): 后台 wait_for_resume(timeout=None) 与前端
#   task_pause_check_and_yield(timeout=300) 口径不一; 且 _pause_core 超时分支仅清 _was_paused 不清 paused 不 set 事件,
#   300s 后后台路径仍无限等、前端路径醒来即空转, 任务真实卡在 SUSPENDED 永不结束。修复: ①常量
#   _PAUSE_AUTO_RESUME_TIMEOUT(DRY 消魔数); ②wait_for_resume 默认改该常量(口径一致); ③超时分支改真恢复
#   (复用 set_resumed: 清paused+置running+set事件, 双路径一同醒来继续), 暂停期间已取消则不自动恢复。
#   compliance: KISS-DIRECT/DRY/SRP/禁止backward
# 2026-10-30 - 小欧 - 取消=任务级取消(北京老陈: 重试中取消必须立即收敛): 置flag+关连接打不断
#   "请求已发出、响应头未到"(TTFB)的等待 —— 本机实测(client_sdk 直连不响应服务端): cancel() 时
#   _current_response 为 None, 取消后仍需等满 provider read_timeout 才结束(6s 超时实测 5.01s;
#   生产 120~200s 即用户所见"约2分钟无cancel终态")。修复: cancel_task 追加 agent_task.cancel(),
#   CancelledError 在任意 await 点立即生效; 终态由 agent_runner 既有 CancelledError 分支+finally
#   守卫产出(唯一生产者, 落库与SSE同源)。配套: task_cancel_check_and_yield 仅在 agent 任务已结束
#   时才合成取消终态(防与 agent 终态重复)。compliance: KISS-DIRECT/DRY/SRP
# 2026-10-30 - 小欧 - R4修复(buffer 已有真实终态时不再合成): task_cancel_check_and_yield 新增 task_buffer 参数,
#   取消分支先扫 buffer.event_log 是否已含 type=final —— 已含则返回 None 继续转发。病根: 合成后调用方 return,
#   会把手上这帧(可能正是真实 final)与其后 final_stats 一并截断, 前端拿不到统计/DB 与 SSE 口径分叉。
#   只在取消分支扫描(低频), 不做逐帧 O(n)。compliance: KISS-DIRECT/DRY/SRP
# 2026-10-30 - 小欧 - 取消幂等(cancel_task 重复调用防线): 改用 task_registry.claim_agent_task_for_cancel
#   原子领取"首次打断权", 只有首次真正 cancel agent 协程, 后续重复取消仅落标记。病根: 第二次 cancel()
#   会打断 agent_runner finally 内正在跑的收尾(_publish_final_stats 无 shield、done.set() 在其后),
#   致终态统计丢失、SSE 需等 journal 判死约 60s 才关。判据不用 task["cancelled"](它可能在 agent 协程
#   登记前就被置位, 拿它当判据会丢掉唯一一次打断 in-flight await 的机会)。compliance: KISS-DIRECT/SRP
"""
task_runtime — 运行态任务管理（内存）

合并自: task_state_queries + task_cancel + task_cancel_check
小欧 2026-07-10
"""

import asyncio  # 2026-09-20 小欧 X3修复: _pause_core 已用 asyncio.wait_for/TimeoutError 却未import, 暂停超时均NameError — 小欧-2026-09-20
import time
from datetime import datetime
from typing import Optional, AsyncGenerator

from app.logger import logger, log_and_print  # 2026-09-08 小欧: log_and_print 双写(console可见取消请求) — 小欧-2026-09-08
from app.utils.sse_formatter import format_agent_sse
from app.utils.response_utils import api_success, api_failure
from app.services.task.task_state import (
    check_cancelled, check_paused, check_was_paused,
    get_task_field, get_pause_event, running_tasks_lock, running_tasks,
    StreamBuffer,  # 2026-10-30 小欧 - R4: 取消检查需读 buffer.event_log 判"是否已有真实终态"
)
from app.services.task.task_registry import (
    set_cancelled, pop_task_field,
    set_was_paused, set_resumed, build_step_dict,   # 2026-10-30 小欧 P1: 超时自动恢复复用 set_resumed(DRY)
    claim_agent_task_for_cancel,                    # 2026-10-30 小欧: 取消幂等(首次才打断 agent 协程)
)

from app.services.agent.status_table import set_status, AgentStatus

# 暂停自动恢复超时(秒): 前端 SSE 消费路径(task_pause_check_and_yield)与后台 wait_for_resume 同口径 —
# 暂停最多等该时长, 超时自动恢复继续(防任务永久卡 SUSPENDED 的状态漂移) — 小欧 2026-10-30
_PAUSE_AUTO_RESUME_TIMEOUT = 300.0

# ============================================================
# 取消/暂停操作（从 task_cancel 迁入）
# ============================================================

def _current_step(task_id: str) -> int:
    """取任务的当前轮数(统一步号口径) — 小欧 2026-08-18
    弃用 next_step: 统一读 running_tasks[task_id].agent.llm_call_count,
    or 1 兜底(消费路径可能先于 agent 注册, 防 0 异常)。"""
    _agent = running_tasks.get(task_id, {}).get("agent")
    if _agent is not None:
        return getattr(_agent, "llm_call_count", None) or 1
    return 1


# ============================================================
# 取消来源→用户可见终态文案(方案五 6.6.2 A-G 全覆盖, 北京老陈 2026-09-08)
# ============================================================
CANCEL_SOURCE_TERMINAL_TEXT: dict = {
    "user_requested": "任务已被用户取消",                           # A 人工
    "client_disconnect_timeout": "连接中断多次重连失败，任务已自动取消",  # B 断连重连耗尽(本案例路径)
    "config_limit": "已达最大执行步数限制，任务结束",                  # E 配置限制
    "status_inconsistency": "执行状态异常，任务已结束",               # F 状态异常兜底
    "orchestrator_error": "服务内部异常，任务已终止",                 # G orchestrator 异常自保取消
}


def cancel_terminal_text(source: Optional[str]) -> str:
    """取消来源→终态文案(方案五 6.6.2): 缺省/未知来源回落既有文案"任务已被取消", 兼容原则 — 小欧 2026-09-08"""
    return CANCEL_SOURCE_TERMINAL_TEXT.get(source or "", "任务已被取消")


def _cancel_final_dict(task_id: str, source: Optional[str] = None) -> dict:
    """组装取消终态 step dict(type=final, outcome=cancelled) — 小欧 2026-09-07 4.4.1:
    前端 case 'cancelled' 已删, 取消收尾单一由 type=final+outcome=cancelled 承担。
    禁止 build_step_dict: 其 data 参数会被 MetaStep 包成 data 嵌套, 前端读顶层 outcome 会失效。
    2026-09-08 小欧 方案五: response 按来源出文案, 顶层带 cancel_source 供前端展示/排查(随 step dict 一并落库)。
    2026-09-14 小欧 修复: 统一放 response 字段, 与 FinalStep.to_dict() 对齐(删 content, 前端只读 response)。"""
    return {
        "step": _current_step(task_id),
        "type": "final",
        "outcome": "cancelled",
        "response": cancel_terminal_text(source),  # 2026-09-14 小欧 修复: 取消终态统一放response, 与FinalStep.to_dict()对齐 — 小欧-2026-09-14
        "cancel_source": source or "user_requested",
    }

async def cancel_task(task_id: str, session_id=None, source: str = "user_requested") -> dict:
    cancel_time = datetime.now()
    log_and_print(f"{time.strftime('%H:%M:%S')} [TaskControl] 取消任务 {task_id} source={source}")  # 2026-09-08 小欧: 双写(console可见取消请求) — 小欧-2026-09-08
    success = await set_cancelled(
        task_id,
        cancel_time=cancel_time.isoformat(),
        cancel_request_time=cancel_time.timestamp(),
        cancel_source=source,
    )
    # 方案五 C/D 继承(6.6.2): 来源写回 agent._cancel_source, 使被打断的在飞 LLM 流(handle_answer C路径)
    #   与循环顶检出(D路径)能读到 A/B 原来源, 一个取消动作一个来源(DRY/KISS) — 小欧 2026-09-08
    _task = running_tasks.get(task_id, {})
    _agent = _task.get("agent")
    if _agent is not None:
        _agent._cancel_source = source
    # 修复(小欧 2026-09-20): 取消对象优先 agent 实际使用的 llm_client(会话快照),
    #   而非注册时的全局 ai_service —— 编排 L345-347 已把快照赋给 agent.llm_client, 取消全局单例作用在错误对象。
    #   无 agent / 无 llm_client 时跳过 cancel() — 修复(小欧 2026-09-20): 全局单例可能服务其他会话,
    #   对其调cancel()会误杀, 仅标记cancelled(已由上方set_cancelled完成) — 小欧-2026-09-20
    _cancel_target = None
    if _agent is not None:
        _cancel_target = getattr(_agent, "llm_client", None)
    # 2026-10-30 小欧 - 取消=任务级取消: flag 与关连接都打不断"请求已发出、响应头未到"(TTFB)的等待,
    #   agent 只能等 provider read_timeout(120~200s)才收敛 → 前端等帧看门狗 5s 先到期, 取消终态帧无通道。
    #   task.cancel() 在任意 await 点立即生效; 终态由 agent_runner 的 CancelledError 分支+finally 守卫产出
    #   (唯一生产者, 落库与 SSE 同源), 不另造终态链路。
    #   注意取 agent_task 而非 _task: register_task 在 SSE 请求协程内执行, _task 是 SSE 请求任务(取消它只断
    #   连接、agent 照跑); agent_task 才是编排层 create_task 出来的 agent 协程(stream_orchestrator 注册)。
    #   2026-10-30 小欧 - 幂等: 用 claim_agent_task_for_cancel 只在"首次实际打断"时 cancel, 重复取消仅落标记
    #   (第二次 cancel 会打断 agent_runner finally 的收尾: final_stats 丢失 + done 不置位, SSE 等约 60s)。
    _agent_task = await claim_agent_task_for_cancel(task_id)
    if _agent_task is not None:
        _agent_task.cancel()
        logger.info(f"[Task Cancelled] 任务 {task_id} agent 协程已取消(立即打断在飞 await)")
    else:
        logger.info(f"[Task Cancelled] 任务 {task_id} 无待打断的 agent 协程(已打断过/未登记/已结束), 仅落标记")
    if _cancel_target is not None:
        try:
            await _cancel_target.cancel()
            logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
        except Exception as e:
            logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
    if success:
        logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为cancelled,保留记录")
        return api_success(message=f"任务 {task_id} 已取消", task_status="cancelled", cancel_time=cancel_time.isoformat())
    else:
        logger.warning(f"[TaskControl] 任务 {task_id} 不存在,可能已结束")
        return api_failure(message=f"任务 {task_id} 不存在", task_status="not_found")

# ============================================================
# 取消/暂停检查 + SSE（从 task_cancel_check 迁入）
# ============================================================

async def task_cancel_check_and_yield(
    task_id: str, current_execution_steps: list, task_buffer: StreamBuffer
) -> Optional[str]:
    # 小健 2026-08-17 三堂会审收敛(KISS-DIRECT): 删死参数 session_id/current_content(函数体从未使用, 调用点白算)
    # 小欧 2026-08-18 删 next_step: 步号统一 _current_step(task_id)
    if await check_cancelled(task_id):
        # 2026-09-07 小欧 4.4.1(B9): 去重只认 type=final+outcome=cancelled, 删 type=cancelled
        #   与 incident_value 两枝历史兼容分支(禁止backward; incident_value 线上零生产者, 迁移后亦无,
        #   运行任务只产新契约终态, 单条件即完备)
        # 2026-10-01 小欧 D修: 删任务级 _cancel_sent 标记, 去重只认本连接 execution_steps 列表。
        #   病根: 该标记把去重从连接级提升为任务级, 同一任务的后到连接(重连/新标签页恢复)一律跳过,
        #   收不到 cancelled 终态 → 界面永久停在"执行中"。execution_steps 是每连接专属累积列表
        #   (首连 stream_orchestrator:383 / 重连 :833 均传本连接对象), 列表扫描天然只对本连接去重。
        if any(
            s.get('type') == 'final' and s.get('outcome') == 'cancelled'
            for s in current_execution_steps
        ):
            logger.info(f"[CancelCheck] 任务 {task_id} 本连接已下发cancelled终态,跳过")
            return None
        logger.info(f"[CancelCheck] 任务 {task_id} 取消状态: True")
        # 2026-10-30 小欧 - buffer 已有真实终态(final)时不再合成: 合成后调用方会 return,
        #   把手上这帧(可能正是真实 final)和其后的 final_stats 一起截断, DB/SSE 口径分叉。
        #   只在取消分支扫描(取消是低频事件, 不做逐帧 O(n)); 判据是事件类型不是 offset ——
        #   真实终态一旦产出, 本连接后续必然转发到, 无需二次合成; 重连同理(after_seq 之前已消费)。
        if any(
            (e or {}).get("type") == "final"
            for e in task_buffer.event_log
        ):
            logger.info(f"[CancelCheck] 任务 {task_id} 已有真实终态帧, 不合成(避免截断 final_stats)")
            return None
        # 2026-10-30 小欧 - 终态单生产者: 取消已升级为任务级取消, agent 协程在任意 await 点立即抛出,
        #   由其 agent_runner 的 finally 守卫发布唯一 final(cancelled)(落库+SSE同源)。此处再合成一个会让
        #   同一任务出现两个终态, 且合成帧不落库(DB/SSE 口径分叉)。仅当 agent 任务确已结束(或未注册)时
        #   才由消费侧兜底合成。
        _task_handle = running_tasks.get(task_id, {}).get("agent_task")
        if _task_handle is not None and not _task_handle.done():
            logger.info(f"[CancelCheck] 任务 {task_id} 取消中, agent 仍在收敛, 不合成终态(等其唯一终态帧)")
            return None
        _cancel_source = running_tasks.get(task_id, {}).get("cancel_source")  # 方案五: source 随落库值带出 — 小欧 2026-09-08
        step_dict = _cancel_final_dict(task_id, _cancel_source)
        logger.info(f"[Step] 发送 final(cancelled) 步骤")
        current_execution_steps.append(step_dict)
        return format_agent_sse(step_dict)
    return None


def _emit_step_sse(step: Optional[int], step_type: str, message: str) -> str:
    return format_agent_sse(build_step_dict(step, step_type, message))


async def task_cancel_check(
    task_id: str,
) -> tuple:
    if await check_cancelled(task_id):
        # 4.4.1(2026-09-07 小欧): 启动前取消分支产出改 final+cancelled,
        #   与 task_cancel_check_and_yield 同口径(前端删 case 'cancelled' 后仅认 final 收尾)
        # 2026-09-08 小欧 方案五: source 随落库值带出
        _cancel_source = running_tasks.get(task_id, {}).get("cancel_source")
        logger.info(f"[CancelCheck] 启动前取消(任务启动即终止) task={task_id} source={_cancel_source or 'user_requested'}")  # 2026-09-08 小欧: 消费侧来源跟踪, 补缺日志 — 小欧-2026-09-08
        return True, format_agent_sse(_cancel_final_dict(task_id, _cancel_source))
    return False, ""


async def _pause_core(
    task_id: str,
    timeout: Optional[float],
    emit_sse: bool,
) -> AsyncGenerator[str, None]:
    """暂停阻塞核心: 检测暂停→置SUSPENDED→阻塞等恢复→置THINKING。可选产出SSE。
    拆分依据(三审, 小欧 2026-08-09): 原 task_pause_check 在 react_cycle→agent_runner 路径产出的
    SSE 字符串被 agent_runner 以"跳过非Step事件"丢弃(死路), 但该 SSE 对前端消费路径(openai)是真实所需。
    故拆为两薄封装: wait_for_resume(纯阻塞) / task_pause_check(阻塞+SSE), 职责单一无重复。
    前端暂停提示由 openai._stream_with_control 的 task_pause_check_and_yield 统一下发。"""
    if await check_cancelled(task_id):
        return
    pause_event = await get_pause_event(task_id)
    if pause_event is None:
        return
    is_paused = await check_paused(task_id)
    if not is_paused:
        return
    if not await check_was_paused(task_id):
        await set_was_paused(task_id, True)
        _agent = running_tasks.get(task_id, {}).get("agent")
        if _agent is not None and _agent.status in (AgentStatus.THINKING, AgentStatus.EXECUTING):
            set_status(_agent, AgentStatus.SUSPENDED, "用户暂停任务")
        if emit_sse:
            step_value = _current_step(task_id)
            # 2026-08-28 小欧 yield日志审计: 暂停事件日志(SRP)
            logger.info(f"[pause] task={task_id} step={step_value} paused")
            yield _emit_step_sse(step_value, "paused", '任务已暂停')
    try:
        if timeout:
            await asyncio.wait_for(pause_event.wait(), timeout=timeout)
        else:
            await pause_event.wait()
    except asyncio.TimeoutError:
        logger.warning(f"[task_pause_check] 任务{task_id}暂停超时({timeout}s),自动恢复")
        # 2026-10-30 小欧 P1: 超时=真恢复(复用 set_resumed, DRY): 清 paused+置 running+set 事件,
        #   让后台 wait_for_resume 与前端消费路径一同醒来继续 —— 原实现仅清 _was_paused 不清 paused
        #   不 set 事件, 后台路径仍无限等, 任务永久卡 SUSPENDED/乒乓。暂停期间已取消则不自动恢复
        #   (取消终态由循环顶处理), 仅清 _was_paused。
        if not await check_cancelled(task_id):
            await set_resumed(task_id)
            if emit_sse:
                yield _emit_step_sse(_current_step(task_id), "resumed", '任务已恢复')
        else:
            await set_was_paused(task_id, False)
        return
    if await check_cancelled(task_id):
        return
    await set_was_paused(task_id, False)
    _agent = running_tasks.get(task_id, {}).get("agent")
    if _agent is not None and _agent.status == AgentStatus.SUSPENDED:
        set_status(_agent, AgentStatus.THINKING, "任务已恢复")
    if emit_sse:
        step_value = _current_step(task_id)
        # 2026-08-28 小欧 yield日志审计: 恢复事件日志(SRP)
        logger.info(f"[pause] task={task_id} step={step_value} resumed")
        yield _emit_step_sse(step_value, "resumed", '任务已恢复')


async def wait_for_resume(task_id: str, timeout: Optional[float] = _PAUSE_AUTO_RESUME_TIMEOUT) -> None:
    """仅阻塞等待暂停恢复(不产出SSE)。react_cycle 后台编排路径用 — 小欧 2026-08-09
    SSE 上报统一由前端消费路径 task_pause_check 负责, 后台路径不再产出死路事件。
    2026-10-30 小欧 P1: 默认 timeout 与前端消费路径(task_pause_check_and_yield)同口径,
    防"前端300s自动恢复、后台无限等"双路径状态漂移致任务永久卡死。"""
    async for _ in _pause_core(task_id, timeout, emit_sse=False):
        pass


async def task_pause_check(
    task_id: str,
    timeout: Optional[float] = None,
) -> AsyncGenerator[str, None]:
    """阻塞+产出暂停/恢复SSE。前端SSE消费路径(openai._stream_with_control)用 — 小欧 2026-08-09
    小欧 2026-08-18 删 next_step: 步号统一 _current_step(task_id)"""
    async for sse in _pause_core(task_id, timeout, emit_sse=True):
        yield sse


async def task_pause_check_and_yield(
    task_id: str,
) -> AsyncGenerator[str, None]:
    async for event in task_pause_check(task_id, timeout=_PAUSE_AUTO_RESUME_TIMEOUT):  # 2026-10-30 小欧 P1: 常量 DRY(消魔数300)
        yield event
