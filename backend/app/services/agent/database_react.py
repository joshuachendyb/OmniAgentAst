# -*- coding: utf-8 -*-
"""
DatabaseReactAgent - 数据库操作 ReAct Agent。

P1优先级。

Author: 小健 - 2026-05-06（修正-小沈 2026-05-06：rollback返回False）
"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.prompts.document.database_prompts import DatabasePrompts
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class DatabaseReactAgent(ReactAgentMixin, BaseAgent):
    """数据库操作 ReAct Agent"""
    
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
            raise ValueError("task_id is required for database operation tracking")
        
        effective_category = tool_category or ToolCategory.DOCUMENT
        
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
        
        # Database专用prompts
        self.prompts = DatabasePrompts()
        
        logger.info(f"DatabaseReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("数据库操作")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm_with_summary()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_params = self.executor._normalize_params(action, params)
        return await self.executor.execute(action, normalized_params)
    
    async def rollback(self, step_number=None) -> bool:
        """
        数据库操作无法回滚
        
        Returns:
            False - 表示回滚不可用，而非回滚失败
        """
        logger.warning(f"[DatabaseReactAgent] 数据库操作无法回滚，已执行SQL不会撤销。请手动检查数据状态。")
        return False  # ✅ 更准确的返回值（缺陷4修正）

