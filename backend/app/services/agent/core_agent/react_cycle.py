# -*- coding: utf-8 -*-
"""
run_react_cycle — ReAct 循环核心

小健 - 2026-06-08 替换空占位:实现完整ReAct循环
原文件是死占位,yield not_implemented,导致Agent完全不可用。

逻辑流程:
1. initialize_run_state — 初始化状态
2. while steps < max_steps:
   a. _call_llm → LLM响应
   b. parse_llm_response → 解析为dict
   c. 根据type产出Step并yield
   d. action → _execute_tool → 追加observation
3. final → yield final step

小健 2026-06-08
"""
from typing import Any, Dict, Optional, AsyncGenerator

from app.utils.logger import logger
from app.services.agent.llm_response_parser import parse_llm_response
from app.services.agent.steps import (
    StartStep, ThoughtStep, ActionToolStep,
    ObservationStep, FinalStep, ErrorStep,
    ChunkStep,
)
from app.services.agent.types import AgentStatus


async def run_react_cycle(
    self,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
) -> AsyncGenerator[Any, None]:
    """ReAct循环:调用LLM→解析→执行工具→产出Step"""
    from app.config import get_config
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    # 1. 初始化运行状态
    chunk_buffer, valid_tool_names = self._initialize_run_state(task, task_id, context)

    step_counter = 0
    self.status = AgentStatus.RUNNING

    try:
        while step_counter < max_steps:
            step_counter += 1

            # 2. 调用LLM
            # 构造消息: history + tool observations + new task
            llm_response = await self._call_llm()

            # 3. 检查取消
            if self._cancelled:
                yield self._create_cancelled_chunk()
                break

            # 4. 解析LLM响应
            parsed = parse_llm_response(llm_response)
            parsed_type = parsed.get("type", "parse_error")

            # 4a. reasoning chunk（如果LLM返回了思考过程）
            reasoning = parsed.get("reasoning")
            if reasoning:
                chunk = ChunkStep(
                    step=step_counter,
                    content=reasoning,
                    is_reasoning=True,
                )
                yield self._emit_step(chunk)

            # 4b. 根据类型处理
            if parsed_type == "action" and parsed.get("tool_name"):
                tool_name = parsed["tool_name"]
                tool_params = parsed.get("tool_params", {}) or {}

                # 产出 thought step
                thought = ThoughtStep(
                    step=step_counter,
                    content=parsed.get("thought", ""),
                    tool_name=tool_name,
                    tool_params=tool_params,
                    thought=parsed.get("thought", ""),
                    reasoning=reasoning or "",
                )
                yield self._emit_step(thought)

                # 产出 action step
                action = ActionToolStep(
                    step=step_counter,
                    tool_name=tool_name,
                    tool_params=tool_params,
                )
                yield self._emit_step(action)

                # 执行工具
                result = await self._execute_tool(tool_name, tool_params)
                step_counter += 1

                # 产出 observation step
                observation = ObservationStep(
                    step=step_counter,
                    execution_result=result,
                    tool_name=tool_name,
                )
                yield self._emit_step(observation)

                # 将observation加入conversation history供LLM下一轮使用
                self.message_builder.add_observation(
                    observation_text=str(result)
                )

            elif parsed_type == "answer" or parsed_type == "implicit":
                # 4c. 最终回答
                content = parsed.get("content", "") or llm_response.strip()
                thought = parsed.get("thought", content)

                # 产出 thought step（如果有思考）
                if thought:
                    yield self._emit_step(ThoughtStep(
                        step=step_counter,
                        content=thought,
                        thought=thought,
                        reasoning=reasoning or "",
                    ))

                # 产出 final step
                final = FinalStep(
                    step=step_counter,
                    response=content,
                    thought=thought,
                    reasoning=reasoning or "",
                )
                yield self._emit_step(final)

                self.status = AgentStatus.COMPLETED
                break

            elif parsed_type == "chunk":
                # 4d. 中间内容片段
                content = parsed.get("content", llm_response.strip())
                chunk = ChunkStep(
                    step=step_counter,
                    content=content,
                )
                emitted = self._emit_step(chunk)

                # 累积到chunk buffer
                if chunk_buffer:
                    chunk_buffer.add_chunk(content)
                    if chunk_buffer.is_full:
                        accumulated = chunk_buffer.flush()
                        if accumulated:
                            step_counter += 1
                            yield self._emit_step(ThoughtStep(
                                step=step_counter,
                                content=f"Accumulated {len(accumulated)} chunks",
                            ))
                            yield self._emit_step(ChunkStep(
                                step=step_counter + 1,
                                content=accumulated,
                            ))
                break

            elif parsed_type == "parse_error":
                # 4e. 解析错误
                error_msg = parsed.get("error", "Unknown parse error")
                yield self._exit_with_error(
                    step=step_counter,
                    error_type="parse_error",
                    error_message=error_msg,
                )
                self.status = AgentStatus.FAILED
                break

            else:
                # 4f. 未知类型
                yield self._exit_with_error(
                    step=step_counter,
                    error_type="unknown_parse_type",
                    error_message=f"Unknown parsed type: {parsed_type}",
                )
                self.status = AgentStatus.FAILED
                break

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield self._exit_with_error(
            step=step_counter,
            error_type="runtime_error",
            error_message=str(e),
        )
        self.status = AgentStatus.FAILED

    finally:
        self._on_after_loop()
        self._complete_tracked_task(self.status == AgentStatus.COMPLETED)
