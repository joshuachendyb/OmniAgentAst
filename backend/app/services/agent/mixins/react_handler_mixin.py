# -*- coding: utf-8 -*-
"""
ReActHandlerMixin — ReAct循环响应处理逻辑混入类

合并 11 个子 mixin 到 1 个文件 — 小欧 2026-06-07
清理 _val 过度函数化包装 + getattr 死代码 + 4 次 if not 重复检查 — 小欧 2026-06-07

Author: 小沈 - 2026-05-28
"""
import asyncio
import json
import traceback
from typing import Any, Dict, List, Optional, AsyncGenerator, Set

from app.services.agent.steps import StepFactory
from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.mixins.tool_step_mixin import _ToolStepOutcome
from app.utils.logger import logger
from app.utils.error_classifier import UnifiedErrorClassifier


class ReActHandlerMixin:

    @staticmethod
    def _merge_thought_text(thought: str, content: str) -> str:
        if not thought or not thought.strip():
            return content
        return thought if thought == content else (thought + "\n" + content).strip()

    async def _handle_empty_response(
        self, step_count: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        retry_cnt = self._empty_response_retry_engine.attempt_count
        max_retries = self._empty_response_retry_engine.max_retries
        logger.error(
            f"[空响应] LLM返回空响应 (第{retry_cnt}次重试), "
            f"history长度={len(self.conversation_history)}"
        )
        if retry_cnt > max_retries:
            yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{retry_cnt}次）")
            self._on_after_loop()
            return
        original_len = len(self.conversation_history)
        if original_len <= 4:
            logger.warning("[空响应] 历史已很短无法截断，直接报错")
            yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{retry_cnt}次）")
            self._on_after_loop()
            return
        kept_head = self.conversation_history[:2]
        kept_tail = self.conversation_history[-2:]
        seen_ids = set()
        deduped = []
        for item in kept_head + kept_tail:
            if id(item) not in seen_ids:
                seen_ids.add(id(item))
                deduped.append(item)
        self.conversation_history = deduped
        self.message_builder.conversation_history = deduped
        logger.warning(
            f"[空响应截断历史] 从{original_len}条截断到{len(deduped)}条, "
            f"移除{original_len - len(deduped)}条中间历史, 准备重试"
        )
        yield StepFactory.create_incident_step(
            step=step_count,
            incident_value='retrying',
            message=f"AI返回空响应，已压缩对话历史重试（第{retry_cnt}次）"
        )

    def _handle_run_exception(self, e: Exception, step_count: int) -> Dict[str, Any]:
        self.message_builder.temp_history.clear()
        traceback.print_exc()
        logger.error(f"Agent run_stream error: {e}", exc_info=True)
        return self._exit_with_error(step_count, "unhandled_exception", str(e))

    async def _handle_chunk_type(
        self, parsed: Dict[str, Any], step_count: int,
        chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._parse_retry_engine.reset_attempts()
        chunk_content = parsed.get("content", "")
        chunk_buffer.append(chunk_content)
        self.message_builder.temp_history.append({"role": "assistant", "content": chunk_content})
        if len(self.message_builder.temp_history) > 10:
            self.message_builder.temp_history = self.message_builder.temp_history[-10:]
        yield self._emit_step(StepFactory.create_chunk_step(step=step_count, content=chunk_content))
        if chunk_buffer.should_force_stop():
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, "chunk累积超时，强制停止"):
                yield step
            return
        if self.tool_category is None or chunk_buffer.should_promote():
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, ""):
                yield step

    async def _complete_chunk(
        self, content: str, step_count: int, thought: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if content:
            self.message_builder.temp_history.clear()
            self.message_builder.add_assistant(content)
        yield self._emit_step(StepFactory.create_final_step(step=step_count + 1, response=content, thought=thought))
        self.status = AgentStatus.COMPLETED
        self._on_after_loop()

    async def _handle_completion_type(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._parse_retry_engine.reset_attempts()
        if chunk_buffer.buffer:
            content = chunk_buffer.flush()
            if content:
                self.message_builder.temp_history.clear()
                self.message_builder.add_assistant(content)
        # 4 个字段中找第一个非空(DRY:消除 4 次 if not 重复)
        answer_response = next(
            (parsed.get(k, "") for k in ("response", "content", "reasoning") if parsed.get(k, "").strip()),
            ""
        )
        if not answer_response:
            tool_params = parsed.get("tool_params", {})
            if isinstance(tool_params, dict):
                result = tool_params.get("result", "")
                if isinstance(result, str) and result.strip():
                    answer_response = result
        yield self._emit_step(StepFactory.create_final_step(
            step=step_count, response=answer_response, thought=parsed.get("reasoning", "")
        ))
        self.status = AgentStatus.COMPLETED

    async def _handle_thought_only(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._parse_retry_engine.reset_attempts()
        thought = self._merge_thought_text(parsed.get("thought", ""), parsed.get("content", ""))
        yield self._emit_step(StepFactory.create_thought_step(
            step=step_count, content="", tool_name="", tool_params={},
            thought=thought, reasoning=parsed.get("reasoning", "")
        ))
        self.message_builder.add_assistant(thought)
        self.message_builder.trim_history()
        chunk_buffer.clear()

    async def _handle_parse_error(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        error_msg = parsed.get("error", "Unknown parse error")
        chunk_buffer.clear()
        is_network_error, error_type = UnifiedErrorClassifier.is_network_or_api_error(error_msg)
        if not is_network_error:
            self.message_builder.add_observation(
                f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format (Thought -> Action -> Action Input)."
            )
        else:
            logger.info(f"[parse_react_response] 网络/API错误，不注入history: {error_msg}")
            if error_type == "api_error_429":
                retry_delay = self._parse_retry_engine.current_delay
                logger.warning(f"[parse_react_response] 429限流, 等待{retry_delay:.0f}s后重试 (第{self._parse_retry_engine.attempt_count+1}次)")
                await asyncio.sleep(retry_delay)
            yield StepFactory.create_incident_step(
                step=step_count,
                incident_value='rate_limit',
                message=f"API暂时不可用，正在重试（第{self._parse_retry_engine.attempt_count + 1}次）"
            )
        self._parse_retry_engine.record_attempt()
        if self._parse_retry_engine.exhausted:
            yield self._exit_with_error(step_count, "parse_error", f"解析失败: {error_msg}（已重试{self._parse_retry_engine.max_retries}次）")
            self._on_after_loop()
            return
        yield StepFactory.create_incident_step(
            step=step_count,
            incident_value='retrying',
            message=f"解析失败，正在重试（第{self._parse_retry_engine.attempt_count}次）"
        )

    async def _handle_action_type(
        self, parsed: Dict[str, Any], step_count: int,
        chunk_buffer: ChunkBuffer, valid_tool_names: Set[str],
        task_id: Optional[str],
        response: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._parse_retry_engine.reset_attempts()
        if chunk_buffer.buffer:
            content = chunk_buffer.flush()
            if content:
                self.message_builder.temp_history.clear()
                self.message_builder.add_assistant(content)
        thought = self._merge_thought_text(parsed.get("thought", ""), parsed.get("content", ""))
        yield self._emit_step(StepFactory.create_thought_step(
            step=step_count, content="", tool_name=parsed.get("tool_name"),
            tool_params=parsed.get("tool_params", {}), thought=thought,
            reasoning=parsed.get("reasoning", "")
        ))
        self.status = AgentStatus.EXECUTING
        outcome = await self._execute_tool_step(
            parsed.get("tool_name"), parsed.get("tool_params", {}), step_count
        )
        async for step in self._handle_observation_flow(outcome, parsed, step_count, task_id):
            yield step

    async def _handle_observation_flow(
        self, outcome: _ToolStepOutcome, parsed: Dict[str, Any],
        step_count: int, task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self.status = AgentStatus.OBSERVING
        self.message_builder.add_observation(
            outcome.obs_inject_text, self.llm_call_count, fc_context=outcome.obs_fc_context
        )
        yield outcome.observation_step
        if outcome.is_done:
            data = outcome.execution_result.get("data")
            try:
                response_text = json.dumps(data, ensure_ascii=False) if data is not None else ""
            except (TypeError, ValueError):
                response_text = str(data)
            msg = outcome.execution_result.get("message", "")
            if msg:
                response_text = msg + "\n" + response_text
            yield self._emit_step(StepFactory.create_final_step(
                step=step_count, response=response_text, thought="工具执行要求直接返回结果"
            ))
            self.status = AgentStatus.COMPLETED
            self._on_after_loop()
            return
        self.message_builder.trim_history()
        pending_calls = parsed.get("_pending_calls", [])
        if pending_calls:
            logger.info(f"[ReAct] 主工具完成，继续执行 {len(pending_calls)} 个并行工具")
        async for pd in self._handle_pending_calls(pending_calls, step_count, task_id):
            yield pd

    async def _handle_pending_calls(
        self,
        pending_calls: List[Dict[str, Any]],
        step_count: int,
        task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        outcome = None
        for pending in pending_calls:
            step_count += 1
            p_name = pending.get("name", "finish")
            p_params = pending.get("args", {})
            logger.info(f"[ReAct] 执行并行工具: {p_name}")
            outcome = await self._execute_tool_step(p_name, p_params, step_count, is_primary=False)
            yield outcome.action_step
            self.message_builder.add_observation(
                outcome.obs_inject_text, self.llm_call_count, fc_context=outcome.obs_fc_context
            )
        if outcome is not None:
            yield outcome.observation_step
