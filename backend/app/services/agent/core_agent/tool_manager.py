# -*- coding: utf-8 -*-
"""
工具加载和管理

Author: 小沈 - 2026-06-07
"""

from typing import Set

from app.services.tools.tool_queries import get_tools_from_registry_by_category
from app.services.tools.registry import tool_registry
from app.constants import META_TOOL_NAMES
from app.utils.logger import logger


class ToolManager:
    """工具加载和管理"""

    def __init__(self, agent):
        self.agent = agent
        self._agent_cache = {}

    def init_tools(self):
        """初始化工具:meta工具 + 分类工具"""
        self.agent._tools_dict = {}
        self.agent._loaded_categories: Set[str] = set()
        if self.agent.tool_category:
            self.agent._loaded_categories.add(self.agent.tool_category.value)

        # ① 始终加载meta工具(基础能力)
        meta_tool_names = list(META_TOOL_NAMES) if isinstance(META_TOOL_NAMES, (list, tuple, set)) else []
        for name in meta_tool_names:
            impl = tool_registry.get_implementation(name)
            if impl:
                self.agent._tools_dict[name] = impl

        # ② 加载分类工具
        if self.agent.tool_category:
            category_tools = get_tools_from_registry_by_category(tool_registry, self.agent.tool_category)
            self.agent._tools_dict.update(category_tools)

        logger.info(f"[ToolManager] 初始化完成,共{len(self.agent._tools_dict)}个工具,分类={self.agent._loaded_categories}")

    def _clear_cache(self, *keys):
        """清除缓存 — 替代delattr黑魔法"""
        for key in keys:
            self._agent_cache.pop(key, None)

    def get_cache(self, key: str, default=None):
        """获取缓存"""
        return self._agent_cache.get(key, default)

    def set_cache(self, key: str, value):
        """设置缓存"""
        self._agent_cache[key] = value

    def load_by_intent(self, intent_type: str, reason: str = ""):
        from app.services.intents.intent_mapper import resolve_category
        category = resolve_category(intent_type)
        if not category:
            logger.warning(f"[动态加载] 意图'{intent_type}'无对应工具分类")
            return
        if category.value in self.agent._loaded_categories:
            return

        logger.info(f"[动态加载] 原因: {reason},加载意图: {intent_type},分类: {category.value}")
        new_tools = get_tools_from_registry_by_category(tool_registry, category)

        self.agent._tools_dict.update(new_tools)
        self.agent._loaded_categories.add(category.value)

        new_tool_names = sorted(new_tools.keys())
        logger.info(f"[动态加载] 已加载{intent_type}分类的{len(new_tool_names)}个工具")

        self.refresh_fc_tools(category)

        self._clear_cache('_cached_schema_text', '_cached_tools_content', '_last_injected_categories')

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def refresh_fc_tools(self, category):
        """刷新FC通道的tools定义"""
        if hasattr(self.agent, 'tools_strategy') and self.agent.tools_strategy is not None and hasattr(self.agent, 'openai_tools') and self.agent.openai_tools:
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.agent.openai_tools.extend([t for t in new_openai_tools if t not in self.agent.openai_tools])
            self.agent.tools_strategy.tools = self.agent.openai_tools
            logger.info(f"[FC刷新] tools定义已更新,当前{len(self.agent.openai_tools)}个")
