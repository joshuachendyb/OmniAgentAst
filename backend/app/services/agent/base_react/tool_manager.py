# -*- coding: utf-8 -*-
"""
工具加载和管理 — 从 base_react.py 拆出

复制来源: base_react.py 第133-145行 (_init_tools), 第220-267行 (load_tools_by_intent)
Author: 小沈 - 2026-05-31
"""

from typing import Set

from app.services.tools.tool_queries import get_tools_from_registry_by_category
from app.constants import META_TOOL_NAMES
from app.utils.logger import logger


class ToolManager:
    """工具加载和管理（SRP）"""

    def __init__(self, agent):
        self.agent = agent

    def init_tools(self):
        """复制自 base_react.py 第133-145行 — 初始化工具"""
        self.agent._tools_dict = {}
        self.agent._loaded_categories: Set[str] = set()
        if self.agent.tool_category:
            self.agent._loaded_categories.add(self.agent.tool_category.value)

        # ① 始终加载meta工具（基础能力）
        meta_tools = self.agent._load_tools_by_names(META_TOOL_NAMES)
        self.agent._tools_dict.update(meta_tools)

        # ② 再加载分类工具（merge模式叠加）
        self.agent._init_tools_and_executor(self.agent.tool_category)

    def load_by_intent(self, intent_type: str, reason: str = ""):
        """复制自 base_react.py 第220-267行 — 动态加载某个意图的工具"""
        if intent_type in self.agent._loaded_categories:
            return  # 已加载

        logger.info(f"[动态加载] 原因: {reason}，加载意图: {intent_type}")

        # 1. 获取该意图的工具 - 【2026-05-18 小沈】
        from app.services.intents.intent_mapper import resolve_category
        category = resolve_category(intent_type)
        if not category:
            logger.warning(f"[动态加载] 意图'{intent_type}'无对应工具分类")
            return
        new_tools = get_tools_from_registry_by_category(category)

        # 2. 添加到_tools_dict
        self.agent._tools_dict.update(new_tools)
        self.agent._loaded_categories.add(category.value)

        # 【修复 N4 小沈 2026-05-15】不再注入load_hint，依赖下一轮detail自动包含新分类
        new_tool_names = sorted(new_tools.keys())
        logger.info(f"[动态加载] 已加载{intent_type}分类的{len(new_tool_names)}个工具，下一轮detail将自动包含")

        # 3. 刷新FC通道的tools定义（如果已启用）
        # 【修复 问题2+9 小沈 2026-05-15】增加openai_tools存在性检查
        if hasattr(self.agent, 'tools_strategy') and self.agent.tools_strategy is not None and hasattr(self.agent, 'openai_tools') and self.agent.openai_tools:
            from app.services.tools.registry import tool_registry
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.agent.openai_tools.extend([t for t in new_openai_tools if t not in self.agent.openai_tools])
            self.agent.tools_strategy.tools = self.agent.openai_tools
            logger.info(f"[FC刷新] tools定义已更新，当前{len(self.agent.openai_tools)}个")

        # 【修复 小健 2026-05-24】P2-9: 用try/except替代hasattr+delattr，消除TOCTOU风险
        for _attr in ('_cached_schema_text', '_cached_tools_content', '_last_injected_categories'):
            try:
                delattr(self.agent, _attr)
            except AttributeError:
                pass

        logger.info(f"[动态加载] 完成，新增{len(new_tools)}个工具，总计{len(self.agent._tools_dict)}个")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def refresh_fc_tools(self, category):
        """刷新FC通道的tools定义"""
        if hasattr(self.agent, 'tools_strategy') and self.agent.tools_strategy is not None and hasattr(self.agent, 'openai_tools') and self.agent.openai_tools:
            from app.services.tools.registry import tool_registry
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.agent.openai_tools.extend([t for t in new_openai_tools if t not in self.agent.openai_tools])
            self.agent.tools_strategy.tools = self.agent.openai_tools
            logger.info(f"[FC刷新] tools定义已更新，当前{len(self.agent.openai_tools)}个")
