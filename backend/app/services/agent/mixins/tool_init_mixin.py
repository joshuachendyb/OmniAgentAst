# -*- coding: utf-8 -*-
"""
ToolInitMixin — 工具加载职责混入类

负责：
- _init_tools_and_executor: 初始化工具字典和执行器
- _get_tools_summary: 获取跨分类工具概要
- _get_tools_detail: 获取已加载分类工具的完整描述
- _inject_tools_hint: 工具提示注入（含缓存）
- _inject_schema: Schema文本注入

Author: 小沈 - 2026-05-29 (从react_agent_mixin.py拆分)
Updated: 小沈 - 2026-05-29 (ISP修复: 从PromptBuildMixin移入_inject_tools_hint/_inject_schema)
Updated: 小沈 - 2026-05-30 (ToolExecutor类改为execute_tool_with_unified_retry函数)
"""
from typing import Optional

from app.services.agent.tool_executor import execute_tool_with_unified_retry
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.tool_types import ToolCategory
from app.services.agent.agent_utils.message_utils import inject_tools_info, inject_schema_text, build_schema_text
from app.utils.logger import logger


class ToolInitMixin(ToolLoaderMixin):
    """工具加载职责混入类"""

    def _init_tools_and_executor(self, tool_category: Optional[ToolCategory] = None):
        """初始化工具加载和执行器 - 小沈 2026-05-10"""
        if tool_category:
            self._tools_dict = self.load_tools_by_category(tool_category)
        else:
            self._tools_dict = {}
        self._execute_tool_func = lambda action, params: execute_tool_with_unified_retry(
            action, params, self._tools_dict
        )
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

    def _inject_tools_hint(self, history_dicts, strategy_method):
        """工具提示注入（含缓存） — text策略时注入工具描述，tools策略时不注入 — 小沈 2026-05-29 (从PromptBuildMixin移入)"""
        if strategy_method != "tools":
            try:
                loaded = getattr(self, '_loaded_categories', set())
                _last = getattr(self, '_last_injected_categories', None)
                if _last is None or loaded != _last:
                    detail = self._get_tools_detail()
                    summary = self._get_tools_summary(exclude_categories=loaded)
                    self._cached_tools_content = f"【已加载工具（完整）】\n{detail}\n\n【其他可用工具（概要）】\n{summary}"
                    self._last_injected_categories = frozenset(loaded)
                _cached = getattr(self, '_cached_tools_content', None)
                if _cached:
                    history_dicts = inject_tools_info(history_dicts, _cached)
            except Exception as e:
                logger.warning(f"[ToolSummary] 注入工具概要失败: {e}")
        return history_dicts

    def _inject_schema(self, history_dicts):
        """Schema文本注入 — 小沈 2026-05-21"""
        if not hasattr(self, '_cached_schema_text'):
            self._cached_schema_text = build_schema_text(getattr(self, 'openai_tools', []))
        if self._cached_schema_text:
            history_dicts = inject_schema_text(history_dicts, self._cached_schema_text)
        return history_dicts
