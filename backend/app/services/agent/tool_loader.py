# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 base_agent.py 独立为独立文件(方案A6: ToolLoader与抽象基类解耦):
#   类定义/init_tools/get_tools/load_category 整体复制, 业务逻辑一字不改, 仅新增依赖导入;
#   base_agent.py 同步删除原类定义与 tool_registry 依赖, 工具加载逻辑改由 UniversalAgent.__init__ 驱动
# 2026-08-13 - 小欧 - 三堂会审修复#28: `initial_categories or list(ToolCategory)` 显式空set()为假值→回退"全部"
#   【病根】调用方传空集合意图"加载指定(空)"却加载全量, 语义反转; 当前_INITIAL_CATEGORIES非空故潜伏
#   【改法】`list(initial_categories) if initial_categories is not None else list(ToolCategory)`: 空集合=加载指定, None=加载全部
"""
tool_loader — 工具加载器

职责: 初始化/动态加载工具到 agent._tools_dict, 维护 _loaded_categories(单一权威)
从 base_agent.py 独立, 供 UniversalAgent 在实例化时完成工具加载
Author: 小沈 - 2026-06-17 (原名 ToolManager→ToolLoader)
小欧 - 2026-08-12 A6独立
"""
from app.logger import logger
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory


class ToolLoader:
    """工具加载和管理 — 小沈 2026-06-17 改名ToolManager→ToolLoader"""

    def __init__(self, agent):
        self.agent = agent

    def init_tools(self, initial_categories=None):
        """初始化工具,按分类注入工具给LLM"""
        self.agent._tools_dict = {}
        # _loaded_categories 由实际加载结果重建, 保证与_tools_dict一致(单一权威: 只含真正加载了实现的分类)
        # 2026-08-05 小欧: 修复BUG1/2 - 空实现分类不再被标记为已加载; 消除initial_categories=None时标记与实现失配
        self.agent._loaded_categories = set()
        # 2026-08-13 小欧 三堂会审修复#28: 区分None与空集合 — 显式空set()为假值会回退"全部", 与"加载指定(空)"意图反转
        categories_to_load = list(initial_categories) if initial_categories is not None else list(ToolCategory)
        for cat in categories_to_load:
            cat_tools = tool_registry.get_implementations_by_category(cat)
            if cat_tools:
                self.agent._tools_dict.update(cat_tools)
                self.agent._loaded_categories.add(cat)
        logger.info(f"[ToolLoader] 初始化完成,共{len(self.agent._tools_dict)}个工具")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def load_category(self, category: ToolCategory) -> bool:
        """动态加载单个分类的工具到_tools_dict

        单一权威(2026-08-05 小欧 修复BUG1/2):
        - _tools_dict 与 _loaded_categories 同时写入, 保证标记=已实现
        - 返回是否真正加载成功(空实现分类返回False), 供调用方跳过标记
        """
        cat_tools = tool_registry.get_implementations_by_category(category)
        if not cat_tools:
            logger.info(f"[ToolLoader] 分类{category.value}无可用实现, 不标记为已加载")
            return False
        self.agent._tools_dict.update(cat_tools)
        self.agent._loaded_categories.add(category)
        logger.info(f"[ToolLoader] 动态加载分类{category.value}, {len(cat_tools)}个工具")
        return True
