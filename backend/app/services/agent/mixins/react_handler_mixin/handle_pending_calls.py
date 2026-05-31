# -*- coding: utf-8 -*-
"""
_handle_pending_calls — 从 react_handler_mixin.py 拆出

task检查通过 task_registry 函数直接读，不再接收 running_tasks 参数

Author: 小沈 - 2026-05-31
统一: 小健 - 2026-05-31 — 去掉running_tasks参数
"""

from typing import Any, Dict, List, Optional, AsyncGenerator

from app.utils.logger import logger


class HandlePendingCallsMixin:
    """编排并行工具调用列表"""

    async def _handle_pending_calls(
        self,
        pending_calls: List[Dict[str, Any]],
        step_count: int,
        task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第339-371行"""
        outcome = None
        for pending in pending_calls:
            step_count += 1
            p_name = pending.get("name", "finish")
            p_params = pending.get("args", {})
            logger.info(f"[ReAct] 执行并行工具: {p_name}")

            outcome = await self._execute_tool_step(
                p_name, p_params, step_count, is_primary=False
            )
            yield outcome.action_step
            self.message_builder.add_observation(
                outcome.obs_inject_text, self.llm_call_count,
                fc_context=outcome.obs_fc_context
            )
        if outcome is not None:
            yield outcome.observation_step
