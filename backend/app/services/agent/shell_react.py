# -*- coding: utf-8 -*-
"""
ShellReactAgent - Shell命令执行 ReAct Agent

继承ReactAgentMixin+BaseAgent，专用于Shell命令场景。
使用ToolLoaderMixin + tool_category加载工具，无需直接import shell_tools。

Author: 小健 - 2026-05-06（修正-小沈 2026-05-06：rollback返回False）
"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.prompts.shell.shell_prompts import ShellPrompts
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class ShellReactAgent(ReactAgentMixin, BaseAgent):
    """Shell命令执行 ReAct Agent"""
    
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
            raise ValueError("task_id is required for shell operation tracking and safety")
        
        effective_category = tool_category or ToolCategory.SHELL
        
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
        self._init_session()  # 使用Mixin的session管理
        self._init_candidates(candidates)
        
        # Shell专用prompts
        self.prompts = ShellPrompts()
        
        logger.info(f"ShellReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("Shell命令")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task, context)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm_with_summary()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_params = self.executor._normalize_params(action, params)
        return await self.executor.execute(action, normalized_params)
    
    async def rollback(self, step_number=None) -> bool:
        """
        Shell命令无法回滚
        
        Returns:
            False - 表示回滚不可用，而非回滚失败
        """
        logger.warning(f"[ShellReactAgent] Shell命令无法回滚，已执行命令不会撤销。请手动检查系统状态。")
        return False  # ✅ 更准确的返回值（缺陷4修正）
