# -*- coding: utf-8 -*-
"""
ReActHandlerMixin — ReAct循环处理逻辑混入类

从 base_react.py 拆出，遵循 SRP：
- BaseAgent：ReAct循环骨架 + 状态初始化 + 抽象方法 + Hook + 工具方法
- ReActHandlerMixin：所有 _handle_* / _execute_* 响应处理逻辑

Author: 小沈 - 2026-05-28
"""

import asyncio
import json
import traceback
from typing import Any, Dict, List, Optional, Set, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.types import AgentStatus
from app.utils.error_classifier import UnifiedErrorClassifier
from app.utils.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.mixins.tool_step_mixin import _ToolStepOutcome


class ReActHandlerMixin:
    """ReAct循环响应处理逻辑 — 小沈 2026-05-28

    本混入类依赖宿主（BaseAgent及其子类）提供以下属性/方法：
    - self.conversation_history (property)
    - self.message_builder
    - self.status
    - self._parse_retry_engine / self._empty_response_retry_engine
    - self.llm_call_count
    - self.tool_category
    - self._emit_step()
    - self._exit_with_error()
    - self._check_interrupt()
    - self._on_after_loop()
    - self._execute_tool_step()
    """

    @staticmethod
    def _merge_thought_text(thought: str, content: str) -> str:
        """合并 thought 和 content 文本 — 小沈 2026-05-28"""
        _val = content
        if thought and thought.strip():
            _val = thought if thought == content else (thought + "\n" + content).strip()
        return _val

    async def _handle_empty_response(
        self, step_count: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """空响应截断历史重试 — 小沈 2026-05-25"""
        _retry_cnt = self._empty_response_retry_engine.attempt_count
        _max_retries = self._empty_response_retry_engine.max_retries
        logger.error(
            f"[空响应] LLM返回空响应 (第{_retry_cnt}次重试), "
            f"history长度={len(self.conversation_history)}"
        )

        if _retry_cnt > _max_retries:
            yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{_retry_cnt}次）")
            self._on_after_loop()
            return

        original_len = len(self.conversation_history)
        if original_len <= 4:
            logger.warning("[空响应] 历史已很短无法截断，直接报错")
            yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{_retry_cnt}次）")
            self._on_after_loop()
            return

        kept_head = self.conversation_history[:2]
        kept_tail = self.conversation_history[-2:]
        seen_ids: Set[int] = set()
        deduped = []
        for item in kept_head + kept_tail:
            item_id = id(item)
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                deduped.append(item)
        removed_len = original_len - len(deduped)
        self.conversation_history = deduped
        self.message_builder.conversation_history = deduped
        logger.warning(
            f"[空响应截断历史] 从{original_len}条截断到{len(deduped)}条, "
            f"移除{removed_len}条中间历史, 准备重试"
        )
        yield StepFactory.create_incident_step(
            step=step_count,
            incident_value='retrying',
            message=f"AI返回空响应，已压缩对话历史重试（第{_retry_cnt}次）"
        )

    async def _handle_chunk_type(
        self, parsed: Dict[str, Any], step_count: int,
        chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """chunk类型处理：拼接buffer、阈值检测、无工具Agent退出 — 小沈 2026-05-30"""
        self._parse_retry_engine.reset_attempts()
        chunk_content = parsed.get("content", "")

        # 1. 存入buffer
        chunk_buffer.append(chunk_content)

        # 2. 存入message_builder历史（保留最近10条）
        self.message_builder.temp_history.append({"role": "assistant", "content": chunk_content})
        if len(self.message_builder.temp_history) > 10:
            self.message_builder.temp_history = self.message_builder.temp_history[-10:]

        # 3. 立即显示这个chunk
        chunk_step = StepFactory.create_chunk_step(step=step_count, content=chunk_content)
        yield self._emit_step(chunk_step)

        # 4. 检查是否该"倒水"完成
        # 【3.9修复 北京老陈 2026-05-31】chunk累积超时检测，防止无限循环
        if chunk_buffer.should_force_stop():
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, "chunk累积超时，强制停止"):
                yield step
            return

        if self.tool_category is None:
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, ""):
                yield step
            return

        if chunk_buffer.should_promote():
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, ""):
                yield step
            return

    async def _complete_chunk(
        self, content: str, step_count: int, thought: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """chunk完成的公共逻辑：builder操作 + final_step + COMPLETED — 北京老陈 2026-05-31
        
        【DRY+SLAP修复】只接收content参数，不依赖ChunkBuffer
        """
        # builder操作：清空历史，保存accumulated内容
        if content:
            self.message_builder.temp_history.clear()
            self.message_builder.add_assistant(content)

        # 创建final_step
        final_step = StepFactory.create_final_step(step=step_count + 1, response=content, thought=thought)
        yield self._emit_step(final_step)

        # 标记完成
        self.status = AgentStatus.COMPLETED
        self._on_after_loop()

    async def _handle_completion_type(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """answer/implicit完成处理 — 小沈 2026-05-25"""
        self._parse_retry_engine.reset_attempts()

        if chunk_buffer.buffer:
            content = chunk_buffer.flush()
            if content:
                self.message_builder.temp_history.clear()
                self.message_builder.add_assistant(content)

        answer_response = parsed.get("response", "")
        if not answer_response or not answer_response.strip():
            answer_response = parsed.get("tool_params", {}).get("result", "") if isinstance(parsed.get("tool_params"), dict) else ""
        if not answer_response or not answer_response.strip():
            answer_response = parsed.get("content", "")
        if not answer_response or not answer_response.strip():
            answer_response = parsed.get("reasoning", "")

        _reasoning = parsed.get("reasoning", "")
        final_step = StepFactory.create_final_step(
            step=step_count, response=answer_response, thought=_reasoning,
            model=getattr(self, 'model', None), provider=getattr(self, 'provider', None)
        )
        yield self._emit_step(final_step)
        self.status = AgentStatus.COMPLETED

    async def _handle_thought_only(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """thought_only纯思考分支 — 小沈 2026-05-25"""
        self._parse_retry_engine.reset_attempts()
        thought = parsed.get("thought", "")
        thought_content = parsed.get("content", "")

        _thought_val = self._merge_thought_text(thought, thought_content)

        thought_step = StepFactory.create_thought_step(
            step=step_count, content="", tool_name="", tool_params={},
            thought=_thought_val, reasoning=parsed.get("reasoning", "")
        )
        yield self._emit_step(thought_step)
        self.message_builder.add_assistant(_thought_val)
        self.message_builder.trim_history()
        chunk_buffer.clear()

    async def _handle_parse_error(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """解析错误重试 — 委托调用点2引擎 — 小沈 2026-05-25"""
        error_msg = parsed.get("error", "Unknown parse error")
        chunk_buffer.clear()

        is_network_error, _error_type = UnifiedErrorClassifier.is_network_or_api_error(error_msg)

        if not is_network_error:
            self.message_builder.add_observation(
                f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format (Thought -> Action -> Action Input)."
            )
        else:
            logger.info(f"[parse_react_response] 网络/API错误，不注入history: {error_msg}")
            if _error_type == "api_error_429":
                _retry_delay = self._parse_retry_engine.current_delay
                logger.warning(f"[parse_react_response] 429限流, 等待{_retry_delay:.0f}s后重试 (第{self._parse_retry_engine.attempt_count+1}次)")
                await asyncio.sleep(_retry_delay)
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
        running_tasks: Optional[Dict[str, Any]], task_id: Optional[str],
        response: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """action工具执行入口 — 小沈 2026-05-30"""
        tool_name = parsed.get("tool_name")
        tool_params = parsed.get("tool_params", {})
        thought_content = parsed.get("content", "")
        thought = parsed.get("thought", "")
        reasoning = parsed.get("reasoning", "")

        self._parse_retry_engine.reset_attempts()

        chunk_buffer_was_flushed = bool(chunk_buffer.buffer)
        if chunk_buffer.buffer:
            content = chunk_buffer.flush()
            if content:
                self.message_builder.temp_history.clear()
                self.message_builder.add_assistant(content)

        _thought_val = self._merge_thought_text(thought, thought_content)

        thought_step = StepFactory.create_thought_step(
            step=step_count, content="", tool_name=tool_name,
            tool_params=tool_params, thought=_thought_val, reasoning=reasoning
        )
        yield self._emit_step(thought_step)

        self.status = AgentStatus.EXECUTING

        _int = self._check_interrupt(step_count, running_tasks)
        if _int:
            yield _int
            self._on_after_loop()
            return

        outcome = await self._execute_tool_step(tool_name, tool_params, step_count, is_primary=True)
        yield outcome.action_step

        if not chunk_buffer_was_flushed:
            self.message_builder.add_assistant(response)

        _int = self._check_interrupt(step_count, running_tasks)
        if _int:
            yield _int
            self._on_after_loop()
            return

        async for step in self._handle_observation_flow(
            outcome, parsed, step_count, running_tasks, task_id
        ):
            yield step

    async def _handle_observation_flow(
        self, outcome: _ToolStepOutcome, parsed: Dict[str, Any],
        step_count: int, running_tasks: Optional[Dict[str, Any]],
        task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Observation阶段：结果注入+is_done判断+pending执行 — 小沈 2026-05-25"""
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
            pass

    def _handle_run_exception(self, e: Exception, step_count: int) -> Dict[str, Any]:
        """未捕获异常兜底 — 小沈 2026-05-25"""
        self.message_builder.temp_history.clear()
        traceback.print_exc()
        logger.error(f"Agent run_stream error: {e}", exc_info=True)
        return self._exit_with_error(step_count, "unhandled_exception", str(e))

    async def _handle_pending_calls(
        self,
        pending_calls: List[Dict[str, Any]],
        step_count: int,
        running_tasks: Optional[Dict[str, Any]],
        task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """编排并行工具调用列表 — 小健 2026-05-24

        在主工具Observation完成后执行附带的pending_calls。
        每个调用委托给 _execute_tool_step(is_primary=False)，
        本方法仅负责step递增、中断检查和yield转发。
        返回更新后的step_count供调用方同步。
        """
        for pending in pending_calls:
            step_count += 1
            p_name = pending.get("name", "finish")
            p_params = pending.get("args", {})
            logger.info(f"[ReAct] 执行并行工具: {p_name}")

            if self._check_interrupt(step_count, running_tasks):
                logger.info(f"[Interrupt] 任务 {task_id} 在并行工具执行前被取消")
                break

            outcome = await self._execute_tool_step(
                p_name, p_params, step_count, is_primary=False
            )
            yield outcome.action_step
            self.message_builder.add_observation(
                outcome.obs_inject_text, self.llm_call_count,
                fc_context=outcome.obs_fc_context
            )
        yield outcome.observation_step
