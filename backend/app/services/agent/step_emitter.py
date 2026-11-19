
# -*- coding: utf-8 -*-
"""
step_emitter — 步骤发射和Task追踪

task检查由 run_sse_stream 层处理,本层不碰
编辑历史:
Author: 小沈 - 2026-05-31
2026-05-31 小健 — 删除check_cancelled调用
2026-07-16 小欧  统一TaskID: _get_tracker只返回tracker, complete_task/record_operation直读agent.task_id
2026-07-22 小欧  emit注入FinalStep._accumulated_usage: 自动从agent.accumulated_usage读取
2026-07-22 小欧  emit注入加is None防御: 仅外部未设置时才注入
2026-08-18 - 小欧 - error全仅SSE: emit 内记录 _last_error(type=="error" 时读 _kwargs 取 error_type/error_message, 赋值 agent._last_error, KISS-DIRECT单一出口)
# 2026-08-20 - 小欧 - 11.1 token 四层同构: emit FinalStep 时自动注入 task/session/chain_accumulated_tokens 三层累计(读 agent 内存态, 与 react_cycle yield 值一致); 仅 FinalStep 触发, 仅外部未设置时注入
2026-08-18 - 小欧 - 三堂会审复核: ①emit._last_error 兼容 ErrorStep 载体(_kwargs 为空时回退读 error_type 属性), 防 error_type 丢失; ②删除死码 exit_with_error 及 ErrorStep import(YAGNI, 全仓无真实调用点)
2026-08-28 小欧 - yield日志审计: emit()统一入口加 logger.debug("[StepEmit] type step"), 覆盖全部~50个Step yield(KISS+DRY, 单一日志出口), 三堂会审无逻辑修正
2026-08-28 小欧 - KISS修正(三堂会审yield链审查): emit_final_with_stats 由 async def 改 sync 返回 (final, stats) 二元组; 原 async 体内零await, 纯伪异步包装, 逼出10处调用点写 async for 仪式代码; 调用点 async for→for, 行为等价无backward
2026-09-04 小健 - SLAP修复: emit_final_with_stats 从 final_step 提取 outcome 并透传给 build_final_stats_step(outcome=...), 消除发射层对遥测层隐式依赖 — 小健-2026-09-04
# 2026-09-05 小健 - answer_focus第一阶段(10.3)搬二(8.2): 新增终态工厂 emit_completed_final/emit_failed_final,
#   收口handler侧5处终态分产(顺序敏感set_failed内聚一步) - 小健-2026-09-05
# 2026-09-11 小欧 - 方案: emit_final_with_stats 返回一元组(final,); final_stats 移出循环链由 runner 延后单发 — 小欧-2026-09-11
# 2026-09-11 小欧 - 修复: emit() 注入 model/provider(任务快照优先) + duration(now - telemetry._run_start_ts),
#   根因: emit_completed_final/emit_failed_final 未传 final_model/duration 致 DB step_json 三字段 null — 小欧-2026-09-11
# 2026-10-25 小欧 - 通知信封收敛: 新增 emit_notice() 统一发射器(三堂会审 DRY), 消除 start_step/tool_executor 重复实现;
#   信封结构 type="notice" + kind + phase + content, 仅 SSE 不落库(走 SSE_ONLY_TYPES) — 小欧-2026-10-25
# 2026-10-25 小欧 - emit_notice 内补 log_and_print(北京老陈令): 统一出口记控制台日志, 所有 notice(压缩/装包×start/done/failed)一处覆盖(DRY) — 小欧-2026-10-25
# 2026-11-03 小欧 - log_and_print 增 level 参数: emit_notice 日志显式传 level="WARNING"(控制台默认档可见通知) — 小欧-2026-11-03
# 2026-11-18 商量 - 新增 ask_question: 经 question_gateway 发阻塞问询事件(SSE), buffer 判空同 emit_notice, 供 tool_executor 注入回调
# 2026-11-18 商量 - 三堂会审整改: ask_question 无缓冲区改抛 RuntimeError(经工具层 except 收口为"问询通道异常, 自行决策继续"), 不再伪造 cancelled 误报"用户已放弃"
# 2026-11-18 商量 - 超时双分支镜像 hitl_confirm: HTL开=security.hitl.timeout 窗, HTL关=bypass 短窗自动过(仍要问), 公式单源复用 _resolve_timeouts
# 2026-11-18 商量 - 三堂会审复核: 窗口模式(auto_confirm=not enabled)随调一道下传网关并回传工具层,
#   消除工具层二次读配置致"窗口与兜底文案错配" — 商量-2026-11-18
# 2026-11-19 小欧 - emit_notice 加可选 items 结构化载荷(schedule 清单), 经 MetaStep **kwargs 透传下发 notice 帧;
#   其它 notice 不传为 None, 行为不变。
# 2026-11-19 小欧 - emit_notice 加可选 only_event 呈现标记(默认 False=全位置): True=仅事件列表不画卡片不占位置2
#   (schedule error); 纯前端字段不落库不进 LLM, 老 notice 无此字段按默认 False 处理, 兼容零退化。
# 2026-11-19 小欧 - 新增 emit_interact: 通用双向交互事件统一发射器(interaction_id/kind/event/payload),
#   event=ask/answered/cancelled/expired(phase+outcome 合并), question 为第一个使用者, 用专用 InteractStep 类
"""

import time
from typing import Dict, List, Optional

from app.logger import log_and_print, logger
from app.services.agent.steps import (  # 2026-11-03 小欧 - 补 ReasoningStep: emit() 返回注解此前引用悬空名
    FinalStep,
    ReasoningStep,
)


class StepEmitter:
    """步骤发射和Task追踪(SRP) — 小健 2026-06-18 提取_get_tracker消除DRY"""

    def __init__(self, agent):
        self.agent = agent

    def emit(self, step) -> 'ReasoningStep':
        """记录步骤到agent.steps并返回Step对象"""
        # FinalStep 自动注入三层 token 用量 — 小欧 2026-08-20
        # 仅当外部未设置时才注入，尊重外部传入值
        if isinstance(step, FinalStep):
            if step._accumulated_usage is None:
                step._accumulated_usage = dict(self.agent.accumulated_usage)
            # 11.1 新增：注入任务级/会话级/链级累计（读 agent 内存态，与 react_cycle yield 值一致）
            if step._task_accumulated_tokens is None:
                step._task_accumulated_tokens = dict(getattr(self.agent, "task_accumulated_tokens", {}))
            if step._session_accumulated_tokens is None:
                step._session_accumulated_tokens = dict(getattr(self.agent, "session_accumulated_tokens", {}))
            if step._chain_accumulated_tokens is None:
                step._chain_accumulated_tokens = dict(getattr(self.agent, "chain_accumulated_tokens", {}))
            # 注入 model/provider: 任务快照优先(三堂会审 防还原竞态) — 小欧-2026-09-11
            if step._step_model is None:
                step._step_model = getattr(self.agent, "_task_llm_model", None) or getattr(getattr(self.agent, "llm_client", None), "llm_model", None)
            # 注入 duration: now - telemetry._run_start_ts(同源 build_final_stats_step) — 小欧-2026-09-11
            if step._duration is None:
                _tele = getattr(self.agent, "telemetry", None)
                _start = getattr(_tele, "_run_start_ts", None) if _tele else None
                if _start:
                    step._duration = round(time.time() - _start, 1)
        self.agent.steps.append(step)
        # 2026-08-28 小欧 yield日志审计: Step emit统一入口(覆盖全部~50个Step yield, KISS+DRY)
        logger.debug(f"[StepEmit] {getattr(step, 'type', '?')} step={getattr(step, 'step', '?')}")
        # 2026-08-18 - 小欧 - error全仅SSE, emit统一出口记录_last_error供守卫填充final(KISS-DIRECT单一出口)
        if getattr(step, "type", "") == "error":
            # 2026-08-18 - 小欧 - 三堂会审复核: 兼容两种 error 载体——MetaStep(type="error") 走 _kwargs,
            #   ErrorStep 走 error_type 属性(遗留); 单一出口记录, 保证 error_type 不丢
            _kw = getattr(step, "_kwargs", None) or {}
            _et = _kw.get("error_type", "") or getattr(step, "error_type", "") or "agent_operation_error"
            self.agent._last_error = (_et, step.get_content())
        return step

    def emit_final_with_stats(self, final_step):
        """v1.2 2026-09-11 小欧: 返回一元组 (final,); final_stats 不再由此构建/发布, 改由 runner 延后单发。
        2026-08-28 小欧 KISS修正: 原 async def 但体内零 await, 纯伪异步包装, 逼出10处调用点写 async for 仪式代码;
        改为 sync 返回 (final_step,) 一元组, 调用方 `for _s in ...: yield _s` 即可, 行为等价无backward。
        2026-09-04 小健 SLAP修复: outcome从final_step显式提取并透传给build_final_stats_step, 消除隐式依赖 — 小健-2026-09-04"""
        return (self.emit(final_step),)

    def emit_completed_final(self, step, response, reasoning=""):
        """终态工厂(completed) — 小健 2026-09-05：收口 handler 侧 2 处 completed 分产；
        状态沿用既有机制（dispatch 外层 seen_types→set_completed，本工厂不提前置状态），行为逐字节等价"""
        return self.emit_final_with_stats(FinalStep(
            step=step, response=response, outcome="completed", reasoning=reasoning,
        ))

    def emit_failed_final(self, step, response, error_type="", error_message="", reasoning=""):
        """终态工厂(failed) — 小健 2026-09-05：收口 handler 侧 3 处 failed 分产；
        09-03 顺序铁律内聚于此：set_failed 先行再 emit，使 build_final_stats_step 读到 FAILED"""
        from app.services.agent.status_table import (
            set_failed,  # 延迟 import，随 answer_handler.py:127 既有惯例，防循环依赖 — 小健 2026-09-05
        )
        set_failed(self.agent, error_message or response)
        return self.emit_final_with_stats(FinalStep(
            step=step, response=response, outcome="failed",
            error_type=error_type, error_message=error_message, reasoning=reasoning,
        ))

    async def emit_notice(self, kind: str, phase: str, content: str, items: Optional[List[Dict]] = None,
                          only_event: bool = False) -> None:
        """通知信封统一发射器(事前/事后) — 小欧 2026-10-25 三堂会审

        信封结构: type="notice" + kind(通知种类) + phase(start/done/failed) + content(文案)
        事前(phase=start)与事后(phase=done/failed)共用同一 kind, 前端按 kind+phase 查表渲染。
        buffer 判空: get_stream_buffer 可能返回 None(任务尚未建 buffer), 直接 publish 会 AttributeError。
        2026-11-19 小欧 - items 可选结构化载荷(schedule 清单), 经 MetaStep **kwargs 透传; 其它 notice 不传为 None。
        2026-11-19 小欧 - only_event 呈现标记(默认 False=全位置: 事件列表+卡片+位置2): True=仅事件列表,
          不画卡片不占位置2(schedule error); 纯前端呈现字段, 不落库(notice SSE-only)、不进 LLM,
          老 notice 无此字段前端按默认 False 处理。
        """
        log_and_print(f"[StepEmit] notice {kind}/{phase}: {content[:80]}", level="WARNING")
        try:
            from app.services.agent.steps import MetaStep
            from app.services.task.task_state import get_stream_buffer
            step = self.emit(MetaStep(
                step=len(self.agent.steps), type="notice",
                content=content, kind=kind, phase=phase, items=items, only_event=only_event))
            _buf = get_stream_buffer(self.agent.task_id)
            if _buf is not None:
                await _buf.publish(step.to_dict())
        except Exception as e:        # 播报失败不得影响主链
            logger.warning(f"[StepEmitter] notice 事件播报失败(kind={kind} phase={phase}): {e}")

    async def emit_interact(self, interaction_id: str, kind: str, event: str, content: str = "",
                            payload: Optional[Dict] = None) -> None:
        """通用双向交互事件统一发射器 — 小欧 2026-11-19

        事件契约(框架级, 不认识任何 tool 特殊语义): type=interact + interaction_id + kind
          + event(ask/answered/cancelled/expired, 这条消息发生了什么) + content(文案) + payload(可选, 各 tool 特殊内容)。
        event 为叶子语义(一字段说清事件), phase/outcome 已合并其中; 具体结果值放 payload。
        question 为第一个使用者, 后续交互 tool(confirm/select...)复用本发射器, 只填自己的 kind/payload。
        使用专用 InteractStep 类而非 MetaStep kwargs(字段为框架一等公民, clarity > 复用 kwargs)。
        """
        log_and_print(f"[StepEmit] interact {kind}/{event}: {content[:80]}", level="WARNING")
        try:
            from app.services.agent.steps import InteractStep
            from app.services.task.task_state import get_stream_buffer
            step = self.emit(InteractStep(
                step=len(self.agent.steps), interaction_id=interaction_id, kind=kind,
                event=event, content=content, payload=payload))
            _buf = get_stream_buffer(self.agent.task_id)
            if _buf is not None:
                await _buf.publish(step.to_dict())
        except Exception as e:        # 播报失败不得影响主链
            logger.warning(f"[StepEmitter] interact 事件播报失败(kind={kind} event={event}): {e}")

    async def ask_question(self, questions: list) -> dict:
        """阻塞问询统一发射器 — 商量 2026-11-18

        延迟导入同 emit_notice; buffer 缺失抛 RuntimeError(经工具层 except 收口为"问询通道异常")。
        超时双分支同 hitl_confirm(HITL开=security.hitl.timeout 窗/HTL关=bypass 短窗自动过), 公式单源 _resolve_timeouts。
        窗口模式一并下传(auto_confirm), 兜底文案判据不落到工具层 — 商量-2026-11-18
        返回 {"answers","cancelled","expired","reason","question_id","auto_confirm"}。
        """
        from app.config import get_config
        from app.services.agent.handlers.question_gateway import ask_question
        from app.services.task.task_state import get_stream_buffer

        # 2026-11-18 商量 - 双分支镜像 hitl_confirm(超时公式单源复用 _resolve_timeouts):
        #   HTL开(真人工问询)→backend=security.hitl.timeout(≈120s);
        #   HTL关(bypass, 同 confirm"要问但自动过")→backend=max(MIN+BYPASS_LEAD, auto_confirm_delay) 短窗(≈10s),
        #   到点后端收口 expired, 窗内用户仍可抢答
        _enabled = bool(get_config().get("security.hitl.enabled", True))
        from app.services.agent.handlers.hitl_gateway import _resolve_timeouts
        timeout = int((await _resolve_timeouts(not _enabled))[0])
        _buf = get_stream_buffer(self.agent.task_id)
        if _buf is None:
            # 2026-11-18 商量 - 无缓冲区属基础设施异常, 抛错走工具层"问询通道异常"语义(自行决策继续),
            # 不伪造 cancelled(那会被工具侧误报为"用户已放弃")
            logger.warning("[StepEmitter] ask_question: 无流缓冲区, 无法发射问询事件")
            raise RuntimeError("问询通道不可用: 无流缓冲区")
        # 窗口模式随事件链一道下传: 网关与工具层都按此布尔取兜底文案, 不再各自重读配置(单一真源) — 商量-2026-11-18
        # 2026-11-19 小欧 - 不再传 publish: 网关经 emit_interact 统一发射(start/done), 此处只做 buffer 可用性守卫
        return await ask_question(
            self.agent, questions, timeout=timeout, auto_confirm=not _enabled,
        )

    def _get_tracker(self):
        """获取task_tracker — 小健 2026-06-18 DRY提取, 任务ID直接用 agent.task_id — 小欧 2026-07-16"""
        return getattr(self.agent, '_task_tracker', None)

    def complete_task(self, success: bool):
        """Task追踪:完成任务记录 — 小欧 2026-07-16 删除 _tracked_task_id 别名, 直读 agent.task_id"""
        task_tracker = self._get_tracker()
        if task_tracker:
            try:
                task_tracker.complete_task(self.agent.task_id, success=success)
            except Exception as _e:
                logger.warning(f"[TaskTracker] 完成任务失败: {_e}")

    def record_operation(self, operation_type: str, *, status: Optional[str] = None, error: Optional[str] = None, **kwargs):
        """Task追踪:记录一次操作(调用方传入真实status和error)

        10规范: SRP — 只透传,不判断业务逻辑
        """
        task_tracker = self._get_tracker()
        if task_tracker:
            try:
                task_tracker.add_operation(
                    self.agent.task_id, operation_type, status=status, error=error, **kwargs,
                )
            except Exception as _e:
                logger.warning(f"[TaskTracker] 记录操作失败: {_e}")

