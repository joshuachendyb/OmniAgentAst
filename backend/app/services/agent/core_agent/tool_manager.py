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

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict
