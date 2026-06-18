# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-12 tool_calls原生消费,移除JSON roundtrip
Updated: 小沈 - 2026-06-17 拆分为llm_caller/tool_executor/tool_cache_manager
"""
from typing import Any, List, Optional, Dict, Set

from app.services.agent.core_agent import BaseAgent
from app.services.agent.types import AgentResult
from app.tools.tool_types import ToolCategory
from app.services.prompts.system_prompts import PromptBuilder
from app.utils.logger import logger
from app.utils.cache import TTLCache

from app.services.agent.llm_caller import call_llm
from app.services.agent.tool_executor import execute_tool
from app.services.agent.tool_cache_manager import get_openai_tools, invalidate_tool_cache, patch_search_desc


_INITIAL_CATEGORIES: Set[ToolCategory] = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}


class UniversalAgent(BaseAgent):
    """通用 Agent — 初始仅加载 FUNDAMENTAL+SHELL+FILE,其余分类通过 tool_search 动态注入"""

    TOOL_CACHE_TTL = 300
    _CATEGORIES_CONFIG_CACHE_TTL = 60

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        max_steps: Optional[int] = None,
        initial_categories=None,
        **kwargs
    ):
        if not task_id:
            raise ValueError("task_id is required for operation tracking")

        if max_steps is None:
            from app.config import get_config
            max_steps = get_config().get_max_steps()

        if initial_categories is None:
            initial_categories = _INITIAL_CATEGORIES

        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            max_steps=max_steps,
            initial_categories=initial_categories,
            **kwargs
        )

        self._loaded_categories: Set[ToolCategory] = set(initial_categories)
        self.prompts = PromptBuilder()
        self._tool_cache = TTLCache(ttl=self.TOOL_CACHE_TTL)
        self._categories_config_cache = TTLCache(ttl=self._CATEGORIES_CONFIG_CACHE_TTL)
        self._patch_search_desc()

        logger.info(
            f"UniversalAgent initialized (task_id={task_id})"
        )

    def _get_system_prompt(self) -> str:
        if not hasattr(self, 'prompts') or not self.prompts:
            return "System: 通用助手"
        return self.prompts.build_full_system_prompt()

    def _complete_tracked_task(self, success: bool):
        self._step_emitter.complete_task(success)

    async def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        return await execute_tool(self, tool_name, tool_params)

    async def _call_llm(self):
        async for item in call_llm(self):
            yield item

    def _get_openai_tools(self) -> list:
        return get_openai_tools(self)

    def invalidate_tool_cache(self):
        invalidate_tool_cache(self)

    def _patch_search_desc(self):
        patch_search_desc(self)
