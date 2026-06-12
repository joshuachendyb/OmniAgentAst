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

    def init_tools(self):
        """初始化工具:tool_category为None时加载全部分类(无意图模式)"""
        self.agent._tools_dict = {}
        self.agent._loaded_categories: Set[str] = set()

        # ① 始终加载meta工具
        meta_tool_names = list(META_TOOL_NAMES) if isinstance(META_TOOL_NAMES, (list, tuple, set)) else []
        for name in meta_tool_names:
            impl = tool_registry.get_implementation(name)
            if impl:
                self.agent._tools_dict[name] = impl

        # ② 无tool_category → 加载全部分类(CRSS移除后)
        if not self.agent.tool_category:
            for cat in ToolCategory:
                cat_tools = tool_registry.get_implementations_by_category(cat)
                self.agent._tools_dict.update(cat_tools)
                self.agent._loaded_categories.add(cat.value)
        else:
            # ③ 有tool_category → 只加载该分类
            self.agent._loaded_categories.add(self.agent.tool_category.value)
            category_tools = tool_registry.get_implementations_by_category(self.agent.tool_category)
            self.agent._tools_dict.update(category_tools)

            # ④ 额外加载config.extra_categories
            config = getattr(self.agent, 'config', None)
            if config and hasattr(config, 'extra_categories') and config.extra_categories:
                for extra_cat in config.extra_categories:
                    extra_tools = tool_registry.get_implementations_by_category(extra_cat)
                    self.agent._tools_dict.update(extra_tools)
                    self.agent._loaded_categories.add(extra_cat.value)

        logger.info(f"[ToolManager] 初始化完成,共{len(self.agent._tools_dict)}个工具,分类={self.agent._loaded_categories}")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict
