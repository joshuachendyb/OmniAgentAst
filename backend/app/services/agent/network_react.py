# -*- coding: utf-8 -*-
"""
NetworkReactAgent - 缃戠粶閫氫俊 ReAct Agent

Author: 灏忓仴 - 2026-05-06锛堜慨姝?灏忔矆 2026-05-06锛歳ollback杩斿洖False锛?"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.prompts.network.network_prompts import NetworkPrompts
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class NetworkReactAgent(ReactAgentMixin, BaseAgent):
    """缃戠粶閫氫俊 ReAct Agent"""
    
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
        
        # 鍏敤閫昏緫鍒濆鍖?        self._init_tools_and_executor(effective_category)
        self._init_llm_strategies()
        self._init_task_tracking()()
        self._init_candidates(candidates)
        
        # Network涓撶敤prompts
        self.prompts = NetworkPrompts()
        
        logger.info(f"NetworkReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("缃戠粶閫氫俊")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task, context)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm_with_summary()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_params = self.executor._normalize_params(action, params)
        return await self.executor.execute(action, normalized_params)
    
    async def rollback(self, step_number=None) -> bool:
        """
        缃戠粶閫氫俊鎿嶄綔鏃犳硶鍥炴粴
        
        Returns:
            False - 琛ㄧず鍥炴粴涓嶅彲鐢?        """
        logger.warning(f"[NetworkReactAgent] 缃戠粶閫氫俊鎿嶄綔鏃犳硶鍥炴粴銆傝鎵嬪姩妫€鏌ョ姸鎬併€?)
        return False  # 鉁?缂洪櫡4淇
