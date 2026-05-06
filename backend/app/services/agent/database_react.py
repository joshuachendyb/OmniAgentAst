# -*- coding: utf-8 -*-
"""
DatabaseReactAgent - 鏁版嵁搴撴搷浣?ReAct Agent銆?
P1浼樺厛绾с€?
Author: 灏忓仴 - 2026-05-06锛堜慨姝?灏忔矆 2026-05-06锛歳ollback杩斿洖False锛?"""
from typing import Any, Optional, Dict, List

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
from app.services.prompts.database.database_prompts import DatabasePrompts
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class DatabaseReactAgent(ReactAgentMixin, BaseAgent):
    """鏁版嵁搴撴搷浣?ReAct Agent"""
    
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
        
        effective_category = tool_category or ToolCategory.DATABASE
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        # 鍏敤閫昏緫鍒濆鍖?        self._init_tools_and_executor(effective_category)
        self._init_llm_strategies()
        self._init_task_tracking()()  # 浣跨敤Mixin鐨剆ession绠＄悊
        self._init_candidates(candidates)
        
        # Database涓撶敤prompts
        self.prompts = DatabasePrompts()
        
        logger.info(f"DatabaseReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("鏁版嵁搴撴搷浣?)
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task, context)
    
    async def _get_llm_response(self) -> str:
        return await self._call_llm_with_summary()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_params = self.executor._normalize_params(action, params)
        return await self.executor.execute(action, normalized_params)
    
    async def rollback(self, step_number=None) -> bool:
        """
        鏁版嵁搴撴搷浣滄棤娉曞洖婊?        
        Returns:
            False - 琛ㄧず鍥炴粴涓嶅彲鐢紝鑰岄潪鍥炴粴澶辫触
        """
        logger.warning(f"[DatabaseReactAgent] 鏁版嵁搴撴搷浣滄棤娉曞洖婊氾紝宸叉墽琛孲QL涓嶄細鎾ら攢銆傝鎵嬪姩妫€鏌ユ暟鎹姸鎬併€?)
        return False  # 鉁?鏇村噯纭殑杩斿洖鍊硷紙缂洪櫡4淇锛?
