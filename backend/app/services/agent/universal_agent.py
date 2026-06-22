# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-12 tool_calls原生消费,移除JSON roundtrip
Updated: 小沈 - 2026-06-17 拆分为llm_caller/tool_executor/tool_cache_manager
Updated: 小健 - 2026-06-18 删除 _categories_config_cache（DRY原则）
"""
from typing import Any, List, Optional, Dict, Set

from app.services.agent.core_agent import BaseAgent
from app.services.agent.types import AgentResult
from app.tools.tool_types import ToolCategory
from app.services.prompts.system_prompts import PromptBuilder
from app.utils.logger import logger
from app.utils.cache import TTLCache

from app.services.agent.tool_cache_manager import patch_search_desc


# 初始注入分类 — 小健 2026-06-18
# 注意：注册(register)和注入(inject)是不同概念：
# 1. 注册：在ToolRegistry中注册工具函数，所有工具都在启动时注册
# 2. 注入：将工具描述注入给LLM，只有注入的工具LLM才能看到和使用
_INITIAL_CATEGORIES: Set[ToolCategory] = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}


class UniversalAgent(BaseAgent):
    """通用 Agent — 初始仅注入 FUNDAMENTAL+SHELL+FILE 3个分类给LLM，其余分类通过 tool_search 动态注入"""

    TOOL_CACHE_TTL = 300


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

        self._patch_search_desc()

        logger.info(
            f"UniversalAgent initialized (task_id={task_id})"
        )

    def _get_system_prompt(self) -> str:
        if not hasattr(self, 'prompts') or not self.prompts:
            return "System: 通用助手"
        return self.prompts.build_full_system_prompt()


    def _patch_search_desc(self):
        patch_search_desc(self)
