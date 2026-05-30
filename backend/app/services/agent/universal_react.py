# -*- coding: utf-8 -*-
"""
UniversalReactAgent — 配置驱动的通用 ReAct Agent

改造前：9个Agent子类，8个代码完全相同
改造后：1个通用类 + 声明式配置（AgentConfig）

Author: 小强 - 2026-05-23
"""
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator

from app.services.agent.base_react import BaseAgent
from app.constants import DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.agent.mixins.rollback_mixin import RollbackMixin
from app.services.agent.mixins.tool_step_mixin import ToolStepMixin
from app.services.agent.agent_config import AgentConfig
from app.services.agent.types import AgentResult
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class UniversalReactAgent(ToolStepMixin, ReactAgentMixin, RollbackMixin, BaseAgent):
    """配置驱动的通用 ReAct Agent"""
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        config: AgentConfig,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        if not task_id:
            raise ValueError(f"task_id is required for {config.intent_type} operation tracking")
        
        self.config = config
        effective_category = tool_category or config.category
        effective_max_steps = max_steps or config.max_steps
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=effective_max_steps,
            **kwargs
        )
        
        self._init_tools_and_executor(effective_category)
        self._init_llm_strategies()
        self._init_task_tracking(enable=config.rollback_enabled)
        self._init_candidates(candidates)
        
        self.prompts = config.prompt_class()
        
        logger.info(
            f"UniversalReactAgent initialized "
            f"(intent={config.intent_type}, task_id={task_id}, "
            f"category={effective_category}, rollback={config.rollback_enabled})"
        )
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # 参数归一化由 executor.execute() 内部自动处理，不再手动调用
        return await self.executor.execute(action, params)
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt(self.config.category_display_name)
    
    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.prompts.get_task_prompt(task)
    
    # ===== Hook 实现 =====
    
    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        pass
    
    # ===== run() 方法（file 等需要回滚的 category 使用）=====
    
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
            task_id = self._task_tracker.create_task(
                agent_id=f"{self.config.intent_type}-agent",
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
