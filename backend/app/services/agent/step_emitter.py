
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
2026-08-18 - 小欧 - §10.4.4 P3(error全仅SSE): emit 内记录 _last_error(type=="error" 时读 _kwargs 取 error_type/error_message, 赋值 agent._last_error, KISS-DIRECT单一出口)
# 2026-08-20 - 小欧 - 11.1 token 四层同构: emit FinalStep 时自动注入 task/session/chain_accumulated_tokens 三层累计(读 agent 内存态, 与 react_cycle yield 值一致); 仅 FinalStep 触发, 仅外部未设置时注入
2026-08-18 - 小欧 - 三堂会审复核: ①emit._last_error 兼容 ErrorStep 载体(_kwargs 为空时回退读 error_type 属性), 防 error_type 丢失; ②删除死码 exit_with_error 及 ErrorStep import(YAGNI, 全仓无真实调用点)
"""

from typing import Any, Dict, Optional

from app.services.agent.steps import FinalStep
from app.logger import logger


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
        self.agent.steps.append(step)
        # 2026-08-18 - 小欧 - P3: error全仅SSE, emit统一出口记录_last_error供守卫填充final(KISS-DIRECT单一出口)
        if getattr(step, "type", "") == "error":
            # 2026-08-18 - 小欧 - 三堂会审复核: 兼容两种 error 载体——MetaStep(type="error") 走 _kwargs,
            #   ErrorStep 走 error_type 属性(遗留); 单一出口记录, 保证 error_type 不丢
            _kw = getattr(step, "_kwargs", None) or {}
            _et = _kw.get("error_type", "") or getattr(step, "error_type", "") or "agent_operation_error"
            self.agent._last_error = (_et, step.get_content())
        return step

    async def emit_final_with_stats(self, final_step):
        """final 后单独 yield 终态统计事件 —— 先 .emit(final) 再 .emit(final_stats)，两事件分开、不塞进 final 键体（async 生成器，调用方 async for 转发）— 小欧 2026-08-20"""
        yield self.emit(final_step)
        yield self.emit(self.agent.telemetry.build_final_stats_step())

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

