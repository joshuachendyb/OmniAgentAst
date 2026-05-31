# -*- coding: utf-8 -*-
"""
_handle_observation_flow — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第294-330行
Author: 小沈 - 2026-05-31
"""

import json
from typing import Any, Dict, Optional, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.types import AgentStatus
from app.utils.logger import logger
from app.services.agent.mixins.tool_step_mixin import _ToolStepOutcome


class HandleObservationFlowMixin:
    """Observation阶段处理"""

    async def _handle_observation_flow(
        self, outcome: _ToolStepOutcome, parsed: Dict[str, Any],
        step_count: int, running_tasks: Optional[Dict[str, Any]],
        task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第294-330行"""
        self.status = AgentStatus.OBSERVING
        self.message_builder.add_observation(
            outcome.obs_inject_text, self.llm_call_count, fc_context=outcome.obs_fc_context
        )
        yield outcome.observation_step

        if outcome.is_done:
            _result_data = outcome.execution_result.get("data")
            try:
                _response_text = json.dumps(_result_data, ensure_ascii=False) if _result_data is not None else ""
            except (TypeError, ValueError):
                _response_text = str(_result_data)
            _msg = outcome.execution_result.get("message", "")
            if _msg:
                _response_text = _msg + "\n" + _response_text
            final_step = StepFactory.create_final_step(
                step=step_count, response=_response_text, thought="工具执行要求直接返回结果",
                model=getattr(self, 'model', None), provider=getattr(self, 'provider', None)
            )
            yield self._emit_step(final_step)
            self.status = AgentStatus.COMPLETED
            self._on_after_loop()
            return

        self.message_builder.trim_history()

        pending_calls = parsed.get("_pending_calls", [])
        if pending_calls:
            logger.info(f"[ReAct] 主工具完成，继续执行 {len(pending_calls)} 个并行工具")
        async for _pd in self._handle_pending_calls(pending_calls, step_count, running_tasks, task_id):
            yield _pd
