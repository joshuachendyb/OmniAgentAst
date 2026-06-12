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

    def init_tools(self, initial_categories=None):
        """初始化工具:仅加载initial_categories指定的分类+meta工具"""
        self.agent._tools_dict = {}
        self.agent._loaded_categories: Set[str] = set()

        # ① 始终加载meta工具
        meta_tool_names = list(META_TOOL_NAMES) if isinstance(META_TOOL_NAMES, (list, tuple, set)) else []
        for name in meta_tool_names:
            impl = tool_registry.get_implementation(name)
            if impl:
                self.agent._tools_dict[name] = impl

        # ② 加载指定分类(无指定则加载全部)
        categories_to_load = initial_categories or list(ToolCategory)
        for cat in categories_to_load:
            cat_tools = tool_registry.get_implementations_by_category(cat)
            self.agent._tools_dict.update(cat_tools)
            self.agent._loaded_categories.add(cat.value)

        logger.info(f"[ToolManager] 初始化完成,共{len(self.agent._tools_dict)}个工具,分类={self.agent._loaded_categories}")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict
