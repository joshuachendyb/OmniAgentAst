# -*- coding: utf-8 -*-
"""
工具加载和管理

Author: 小沈 - 2026-06-07
"""

from typing import Set

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.constants import META_TOOL_NAMES
from app.utils.logger import logger


class ToolManager:
    """工具加载和管理"""

    def __init__(self, agent):
        self.agent = agent
        self._agent_cache = {}

    def init_tools(self):
        """初始化工具:meta工具 + 分类工具 + 额外分类工具(声明式配置)"""
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
            category_tools = tool_registry.get_implementations_by_category(self.agent.tool_category)
            self.agent._tools_dict.update(category_tools)

        # ③ 声明式: 额外加载config.extra_categories中的分类工具
        config = getattr(self.agent, 'config', None)
        if config and config.extra_categories:
            for extra_cat in config.extra_categories:
                extra_tools = tool_registry.get_implementations_by_category(extra_cat)
                self.agent._tools_dict.update(extra_tools)
                self.agent._loaded_categories.add(extra_cat.value)
                logger.info(f"[ToolManager] 额外加载{extra_cat.value}分类{len(extra_tools)}个工具")

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
        new_tools = tool_registry.get_implementations_by_category(category)

        self.agent._tools_dict.update(new_tools)
        self.agent._loaded_categories.add(category.value)

        new_tool_names = sorted(new_tools.keys())
        logger.info(f"[动态加载] 已加载{intent_type}分类的{len(new_tool_names)}个工具")

        self.refresh_fc_tools(category)  # no-op for UniversalAgent, kept for interface compat

        self._clear_cache('_cached_schema_text', '_cached_tools_content', '_last_injected_categories', '_cached_openai_tools')

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def refresh_fc_tools(self, category):
        """FC通道tools刷新 — 已废弃，保留接口兼容旧测试
        【P2-5修复 2026-06-09 小沈】UniversalAgent无tools_strategy，此方法为空操作
        """
