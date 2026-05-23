# -*- coding: utf-8 -*-
"""
CodeExecutionReactAgent - Code Execution ReAct Agent.

P3 priority.

Author: xiaojian - 2026-05-06 (Fixed: rollback returns False)
"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.prompts.shell.code_execution_prompts import CodeExecutionPrompts
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class CodeExecutionReactAgent(ReactAgentMixin, BaseAgent):
    """Code Execution ReAct Agent"""
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        if not task_id:
            raise ValueError("task_id is required for code execution tracking")
        
        effective_category = tool_category or ToolCategory.SHELL
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        # Mixin initialization
        self._init_tools_and_executor(effective_category)
        self._init_llm_strategies()
        self._init_task_tracking()  # Use Mixin's session management
        self._init_candidates(candidates)
        
        # CodeExecution specific prompts
        self.prompts = CodeExecutionPrompts()
        
        logger.info(f"CodeExecutionReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("Code Execution")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_params = self.executor._normalize_params(action, params)
        return await self.executor.execute(action, normalized_params)
    
    async def rollback(self, step_number=None) -> bool:
        """
        Code execution operations cannot be rolled back.
        
        Returns:
            False - indicates rollback not available, not rollback failure.
        """
        logger.warning(f"[CodeExecutionReactAgent] Code execution cannot be rolled back. Manually check execution results.")
        return False  # Correct return value (Defect 4 fix)

