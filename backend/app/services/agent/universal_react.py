# -*- coding: utf-8 -*-
"""
UniversalReactAgent — 配置驱动的通用 ReAct Agent

改造前：9个Agent子类，8个代码完全相同
改造后：1个通用类 + 声明式配置（AgentConfig）

继承层级：
  BaseAgent → GenericReactAgent → UniversalReactAgent → DesktopReactAgent

Author: 小强 - 2026-05-23
Updated: 小沈 - 2026-05-30 (config可选+rollback内置+去掉RollbackMixin+覆盖_get_llm_response)
"""
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator

from app.services.agent.generic_react import GenericReactAgent
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.agent.mixins.tool_step_mixin import ToolStepMixin
from app.services.agent.agent_config import AgentConfig
from app.services.agent.types import AgentResult, AgentStatus
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class UniversalReactAgent(ToolStepMixin, ReactAgentMixin, GenericReactAgent):
    """配置驱动的通用 ReAct Agent — 第二层：加工具、加回滚"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        config: Optional[AgentConfig] = None,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        # config变为可选 — 小沈 2026-05-30
        if not task_id:
            intent_type = config.intent_type if config else "unknown"
            raise ValueError(f"task_id is required for {intent_type} operation tracking")

        effective_category = tool_category or (config.category if config else None)
        # 一个地方读取config — 北京老陈 2026-05-31
        if max_steps is None:
            if config and config.max_steps:
                effective_max_steps = config.max_steps
            else:
                from app.config import get_config
                effective_max_steps = get_config().get_max_steps()
        else:
            effective_max_steps = max_steps
        rollback_enabled = config.rollback_enabled if config else True

        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=effective_max_steps,
            rollback_enabled=rollback_enabled,
            candidates=candidates,
            **kwargs
        )

        if config:
            self.config = config
            self.prompts = config.prompt_class()

            logger.info(
                f"UniversalReactAgent initialized "
                f"(intent={config.intent_type}, task_id={task_id}, "
                f"category={effective_category}, rollback={config.rollback_enabled})"
            )
        else:
            logger.info(
                f"UniversalReactAgent initialized "
                f"(task_id={task_id}, category={effective_category})"
            )

    # ===== 必须覆盖：绕过GenericReactAgent的strategy =====

    async def _get_llm_response(self) -> str:
        """直接调LLM，不走strategy — 小沈 2026-05-30"""
        return await self._call_llm()

    # ===== rollback直接定义在这里（不再用RollbackMixin）=====

    async def rollback(self, step_number: Optional[int] = None) -> bool:
        """回滚操作 — 小沈 2026-05-30（从RollbackMixin移入）"""
        try:
            if not self.task_id:
                raise ValueError("Session ID is required for rollback")

            if step_number is None:
                result = await self._execute_tool('rollback_session', {'task_id': self.task_id})
                success = result.get("status") == "success"
            else:
                steps_to_rollback = [s for s in self.steps if s.step_number > step_number]
                if not steps_to_rollback:
                    return False
                success = True
                for step in sorted(steps_to_rollback, key=lambda s: s.step_number, reverse=True):
                    observation = step.observation or {}
                    result_data = observation.get("result", {}) if isinstance(observation, dict) else {}
                    operation_id = result_data.get("operation_id")
                    if operation_id:
                        step_result = await self._execute_tool('rollback_operation', {'operation_id': operation_id})
                        step_success = step_result.get("status") == "success" if isinstance(step_result, dict) else bool(step_result)
                        success = success and step_success
                    else:
                        raise ValueError(f"No operation_id found for step {step.step_number}")

            self.status = AgentStatus.ROLLED_BACK
            return success
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def _get_system_prompt(self) -> str:
        return self._build_system_prompt(self.config.category_display_name)

    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.prompts.get_task_prompt(task)
    
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """运行 Agent 完成任务（非流式）"""
        async with self._lock:
            return await self._run_with_task_tracking(task, context, system_prompt)
    
    async def _run_with_task_tracking(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """内部运行方法（带 session 管理）"""
        task_id = self.task_id or ""
        session_created_by_this_run = False
        
        if not task_id:
            agent_id = f"{self.config.intent_type}-agent" if hasattr(self, 'config') and self.config else "unknown-agent"
            task_id = self._task_tracker.create_task(
                agent_id=agent_id,
                task_description=task
            )
            session_created_by_this_run = True
            self._task_created_by_agent = True
            logger.info(f"Session created in run(): {task_id}")
        
        result = None
        try:
            async for event in self.run_stream(task, context):
                event_type = event.get("type")
                
                if event_type == "final":
                    result = AgentResult(
                        success=True,
                        message=event.get("content", "Task completed successfully"),
                        steps=self.steps,
                        total_steps=len(self.steps),
                        task_id=self.task_id,
                        final_result=event.get("content")
                    )
                elif event_type == "error":
                    result = AgentResult(
                        success=False,
                        message=event.get("message", "Execution failed"),
                        steps=self.steps,
                        total_steps=len(self.steps),
                        task_id=task_id,
                        error=event.get("message")
                    )
            
            if result is None:
                result = AgentResult(
                    success=False,
                    message=f"Exceeded maximum steps ({self.max_steps})",
                    steps=self.steps,
                    total_steps=len(self.steps),
                    task_id=task_id,
                    error="Maximum steps exceeded"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            result = AgentResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                steps=self.steps,
                total_steps=len(self.steps),
                task_id=task_id,
                error=str(e)
            )
            return result
            
        finally:
            if session_created_by_this_run and task_id and self._task_tracker:
                try:
                    success = result.success if result else False
                    self._task_tracker.complete_task(task_id, success=success)
                    logger.info(f"Session completed: {task_id} (success={success})")
                    self._task_created_by_agent = False
                    self.task_id = None
                except Exception as e:
                    logger.error(f"Failed to complete session {task_id}: {e}")
