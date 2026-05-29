# -*- coding: utf-8 -*-
"""
ToolInitMixin — 工具加载职责混入类

负责：
- _init_tools_and_executor: 初始化工具字典和执行器
- _get_tools_summary: 获取跨分类工具概要
- _get_tools_detail: 获取已加载分类工具的完整描述

Author: 小沈 - 2026-05-29 (从react_agent_mixin.py拆分)
"""
from typing import Optional

from app.services.agent.tool_executor import ToolExecutor
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class ToolInitMixin(ToolLoaderMixin):
    """工具加载职责混入类"""

    def _init_tools_and_executor(self, tool_category: Optional[ToolCategory] = None):
        """初始化工具加载和执行器 - 小沈 2026-05-10"""
        if tool_category:
            self._tools_dict = self.load_tools_by_category(tool_category)
        else:
            self._tools_dict = {}
        self.executor = ToolExecutor(self._tools_dict)
        logger.info(f"[{self.__class__.__name__}] 加载工具: {len(self._tools_dict)}个")

    def _get_tools_summary(self, exclude_categories: Optional[set] = None) -> str:
        """获取跨分类工具概要（每轮实时生成） - 小健 2026-05-14

        Args:
            exclude_categories: 排除的分类集合（避免与detail重复）
        """
        from app.services.tools.registry import tool_registry
        return tool_registry.get_all_tools_summary(
            priority_category=self.tool_category or ToolCategory.FILE,
            exclude_categories=exclude_categories
        )

    def _get_tools_detail(self) -> str:
        """获取已加载分类工具的完整描述 - 小健 2026-05-14
        
        【重构 小健 2026-05-15】registry返回的单分类detail已自带"=== 分类名 ==="标题，
        此处只做多分类拼接，不再生成额外标题。
        【2026-05-18 小沈】使用resolve_category支持新旧分类名
        """
        from app.services.tools.registry import tool_registry
        from app.services.intents.intent_mapper import resolve_category
        parts = []
        loaded_cats = getattr(self, '_loaded_categories', set())
        for cat_name in sorted(loaded_cats):
            category = resolve_category(cat_name)
            if not category:
                continue
            try:
                detail = tool_registry.get_all_tools_detail(
                    priority_category=category,
                    category_filter=category
                )
                if detail.strip():
                    parts.append(detail)
            except Exception:
                continue
        return "\n\n".join(parts) if parts else ""
