# -*- coding: utf-8 -*-
"""
run_stream — 从 base_react.py 拆出

复制来源: base_react.py 第191-293行
Author: 小沈 - 2026-05-31
"""

import time
from typing import Any, Dict, Optional, AsyncGenerator

from app.services.agent.types import AgentStatus
from app.services.agent.llm_response_parser import parse_react_response
from app.utils.logger import logger


async def run_stream(
    self,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
    running_tasks: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """复制自 base_react.py 第191-293行 — ReAct 核心循环"""
    if max_steps is None:
        from app.config import get_config
        max_steps = get_config().get_max_steps()
    chunk_buffer, valid_tool_names = self._initialize_run_state(task, task_id, context)
    step_count = 0

    try:
        while True:
            if step_count >= max_steps:
                yield self._exit_with_error(step_count, "max_steps_exceeded", f"已达到最大迭代次数 {max_steps}")
                self._complete_tracked_task(success=False)
                self._on_after_loop()
                return

            step_count += 1

            _int = self._check_interrupt(step_count, running_tasks)
            if _int:
                if task_id and running_tasks:
                    _crt = running_tasks.get(task_id, {}).get("cancel_request_time")
                    if _crt:
                        logger.info(f"[InterruptCheck] 任务 {task_id} 延迟: {(time.time() - _crt) * 1000:.0f}ms")
                yield _int
                self._complete_tracked_task(success=False)
                self._on_after_loop()
                return

            self.status = AgentStatus.THINKING
            response = await self._get_llm_response()

            _int = self._check_interrupt(step_count, running_tasks)
            if _int:
                yield _int
                self._complete_tracked_task(success=False)
                self._on_after_loop()
                return

            if not response:
                self._empty_response_retry_engine.record_attempt()
                self._parse_retry_engine.reset_attempts()
                async for step in self._handle_empty_response(step_count):
                    yield step
                continue

            self._empty_response_retry_engine.reset_attempts()
            parsed = parse_react_response(response)
            parsed_type = parsed["type"]

            if parsed_type == "chunk":
                async for step in self._handle_chunk_type(parsed, step_count, chunk_buffer):
                    yield step
                if self.status == AgentStatus.COMPLETED:
                    self._complete_tracked_task(success=True)
                    return
                continue

            if parsed_type in ("answer", "implicit"):
                async for step in self._handle_completion_type(parsed, step_count, chunk_buffer):
                    yield step
                self._complete_tracked_task(success=True)
                self._on_after_loop()
                return

            if parsed_type == "thought_only":
                async for step in self._handle_thought_only(parsed, step_count, chunk_buffer):
                    yield step
                continue

            thought_content = parsed.get("content", "")
            tool_name = parsed.get("tool_name")
            tool_params = parsed.get("tool_params", {})

            if parsed_type != "parse_error":
                if not tool_name or tool_name not in valid_tool_names:
                    parsed = {"type": "parse_error", "error": f"LLM返回无效工具名: {tool_name!r}"}
                    parsed_type = "parse_error"

            if parsed_type == "parse_error":
                async for step in self._handle_parse_error(parsed, step_count, chunk_buffer):
                    yield step
                continue

            async for step in self._handle_action_type(
                parsed, step_count, chunk_buffer, valid_tool_names,
                running_tasks, task_id, response
            ):
                yield step

    except Exception as e:
        yield self._handle_run_exception(e, step_count)
        self._complete_tracked_task(success=False)
        self._on_after_loop()
        return
