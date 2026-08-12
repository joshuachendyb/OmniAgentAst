# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-12 tool_calls原生消费,移除JSON roundtrip
Updated: 小沈 - 2026-06-17 拆分为llm_caller/tool_executor/tool_cache_manager
Updated: 小健 - 2026-06-18 删除 _categories_config_cache（DRY原则）

编辑历史:
  2026-07-14 小欧 TOOL_CACHE_TTL导入源由base_service改为app.constants(常量集中,非功能退化)
  2026-08-05 小欧 默认注入分类去SHELL: shell工具已迁入FUNDAMENTAL, SHELL分类仅剩which, 不再默认注入(需要时经searchtool动态注入)
  2026-08-12 小欧 A6: 工具加载从 BaseAgent.__init__ 移至本类(方案4.6.3步骤3); 导入 ToolLoader/ToolRetryEngine
"""
from typing import Any, Optional, Set

from app.services.agent import BaseAgent
from app.tools.tool_types import ToolCategory
from app.services.prompts.system_prompts import PromptBuilder
from app.logger import logger
from app.utils.cache import TTLCache

from app.services.agent.tool_loader import ToolLoader
from app.tools.tool_retry_engine import ToolRetryEngine

from app.services.agent.tool_cache_manager import patch_search_desc
from app.constants import TOOL_CACHE_TTL as _TOOL_CACHE_TTL


# 初始注入分类 — 小健 2026-06-18
# 注意：注册(register)和注入(inject)是不同概念：
# 1. 注册：在ToolRegistry中注册工具函数，所有工具都在启动时注册
# 2. 注入：将工具描述注入给LLM，只有注入的工具LLM才能看到和使用
_INITIAL_CATEGORIES: Set[ToolCategory] = {ToolCategory.FUNDAMENTAL, ToolCategory.FILE}


class UniversalAgent(BaseAgent):
    """通用 Agent — 初始仅注入 FUNDAMENTAL+FILE 2个分类给LLM，其余分类（含SHELL）通过 searchtool 动态注入"""

    TOOL_CACHE_TTL = _TOOL_CACHE_TTL


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
            **kwargs
        )

        # 工具加载(A6, 方案4.6.3步骤3): 从 BaseAgent.__init__ 移入本类, 抽象基类不依赖工具注册表
        self._tool_loader = ToolLoader(self)
        self._tool_loader.init_tools(initial_categories=initial_categories)
        self._retry_engine = ToolRetryEngine(self._tools_dict)

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
