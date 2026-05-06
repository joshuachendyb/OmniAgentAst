# -*- coding: utf-8 -*-
"""
NetworkReactAgent - 网络通信 ReAct Agent

Author: 小健 - 2026-05-06（修正-小沈 2026-05-06：rollback返回False）
"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.prompts.network.network_prompts import NetworkPrompts
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class NetworkReactAgent(ReactAgentMixin, BaseAgent):
    """网络通信 ReAct Agent"""
    
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
            raise ValueError("task_id is required for network operation tracking")
        
        effective_category = tool_category or ToolCategory.NETWORK
        
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
        self._init_task_tracking()
        self._init_candidates(candidates)
        
        # Network专用prompts
        self.prompts = NetworkPrompts()
        
        logger.info(f"NetworkReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("网络通信")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task, context)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm_with_summary()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_params = self.executor._normalize_params(action, params)
        return await self.executor.execute(action, normalized_params)
    
    async def rollback(self, step_number=None) -> bool:
        """
        网络通信操作无法回滚
        
        Returns:
            False - 表示回滚不可用
        """
        logger.warning(f"[NetworkReactAgent] 网络通信操作无法回滚。请手动检查状态。")
        return False  # ✅ 缺陷4修正
