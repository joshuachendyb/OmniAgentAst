# -*- coding: utf-8 -*-
"""
DesktopReactAgent - 桌面操作 ReAct Agent。

P1优先级。

Author: 小健 - 2026-05-06（修正-小沈 2026-05-06：rollback返回False）
"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent
from app.constants import DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.agent.mixins.tool_step_mixin import ToolStepMixin
from app.services.prompts.desktop.desktop_prompts import DesktopPrompts
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class DesktopReactAgent(ToolStepMixin, ReactAgentMixin, BaseAgent):
    """桌面操作 ReAct Agent"""
    
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
            raise ValueError("task_id is required for desktop operation tracking")
        
        effective_category = tool_category or ToolCategory.DESKTOP
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        # 公用逻辑初始化
        self._init_tools_and_executor(effective_category)
        self._init_llm_strategies()
        self._init_task_tracking()  # 使用Mixin的任务追踪管理
        self._init_candidates(candidates)
        
        # Desktop专用prompts
        self.prompts = DesktopPrompts()
        
        logger.info(f"DesktopReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("桌面操作")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.agent.tool_executor import execute_tool_with_unified_retry
        return await execute_tool_with_unified_retry(action, params, self._tools_dict)
