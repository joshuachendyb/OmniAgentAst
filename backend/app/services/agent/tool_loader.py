# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 base_agent.py 独立为独立文件(方案A6: ToolLoader与抽象基类解耦):
#   类定义/init_tools/get_tools/load_category 整体复制, 业务逻辑一字不改, 仅新增依赖导入;
#   base_agent.py 同步删除原类定义与 tool_registry 依赖, 工具加载逻辑改由 UniversalAgent.__init__ 驱动
# 2026-08-13 - 小欧 - 三堂会审修复#28: `initial_categories or list(ToolCategory)` 显式空set()为假值→回退"全部"
#   【病根】调用方传空集合意图"加载指定(空)"却加载全量, 语义反转; 当前_INITIAL_CATEGORIES非空故潜伏
#   【改法】`list(initial_categories) if initial_categories is not None else list(ToolCategory)`: 空集合=加载指定, None=加载全部
# 2026-11-27 - 小欧 - 增 excluded_tools(子Agent只读拒绝清单): 清单存 agent._excluded_tools 作单一权威,
#   init_tools 装载与 load_category 动态注入两处同源过滤(searchtool 灌回也被挡), 默认 None 主Agent行为不变
# 2026-11-28 - 小欧 - excluded_tools fail-fast + 别名归一: 传 str 会被 set() 拆成单字符集合致拒绝清单静默失效
#   (安全承诺不得静默降级), 构造期直接 TypeError; 名单统一过 normalize_tool_name, 写别名(write_file)同样生效
# 2026-11-28 - OmniAgent - 名单归一与 str fail-fast 改调 tools_alias_mapper.normalize_name_set():
#   与 tool_description.to_openai_tools 共用同一实现, 消除三处重复表达式(DRY), 行为等价
# 2026-11-28 小欧 - 装载与动态注入时对已注册名也 normalize_tool_name，裸名/别名不能绕过拒绝或白名单
"""
tool_loader — 工具加载器

职责: 初始化/动态加载工具到 agent._tools_dict, 维护 _loaded_categories(单一权威)
从 base_agent.py 独立, 供 UniversalAgent 在实例化时完成工具加载
Author: 小沈 - 2026-06-17 (原名 ToolManager→ToolLoader)
小欧 - 2026-08-12 A6独立
"""
from typing import Optional, Set

from app.logger import logger
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.tools.tools_alias_mapper import normalize_name_set, normalize_tool_name


class ToolLoader:
    """工具加载和管理 — 小沈 2026-06-17 改名ToolManager→ToolLoader"""

    def __init__(self, agent):
        self.agent = agent

    def init_tools(self, initial_categories=None, excluded_tools: Optional[Set[str]] = None,
                   tool_names: Optional[Set[str]] = None):
        """初始化工具,按分类注入工具给LLM

        2026-11-27 小欧 - 增 excluded_tools: 子Agent只读拒绝清单, 存 agent._excluded_tools(单一权威),
          装载时跳过; 与 load_category / 可见性(to_openai_tools exclude)同源, 防 searchtool 动态灌回。
        2026-11-28 小欧 - fail-fast: str 会被 set() 拆成单字符集合(write→{'w','r','i','t','e'})导致
          拒绝清单静默失效, 安全类承诺不接受静默降级, 构造期直接 TypeError; 名字过 normalize_tool_name,
          拒绝名单写别名(write_file)与写注册名(write)等价。
        """
        # 单一权威 — 2026-11-27 小欧; 别名归一 + str fail-fast 收口 normalize_name_set — 2026-11-28 OmniAgent
        self.agent._excluded_tools = normalize_name_set(excluded_tools, "excluded_tools")
        # 小欧 2026-11-28 - 具名白名单: 空集=按分类+拒绝清单(不收窄); 非空=精确放行, 先于 ToolRetryEngine 构造生效
        _names = normalize_name_set(tool_names, "tool_names")
        self.agent._tool_names = _names
        self.agent._tools_dict = {}
        self.agent._loaded_categories = set()
        if _names:
            # 白名单模式: 以已注册全集为源精确取名，分类只用于重建标记(不参与放行判定)
            _all: dict = {}
            for _cat in ToolCategory:
                _all.update(tool_registry.get_implementations_by_category(_cat))
            self.agent._tools_dict = {
                name: impl for name, impl in _all.items()
                if normalize_tool_name(name) in _names
                and normalize_tool_name(name) not in self.agent._excluded_tools
            }
            self.agent._loaded_categories = {
                cat for cat in ToolCategory
                if any(normalize_tool_name(n) in _names
                       for n in tool_registry.get_implementations_by_category(cat))
            }
        else:
            # 2026-08-13 三堂会审修复#28: 区分None与空集合 — 空集合=加载指定(空), 不回退"全部"
            categories_to_load = list(initial_categories) if initial_categories is not None else list(ToolCategory)
            for cat in categories_to_load:
                cat_tools = tool_registry.get_implementations_by_category(cat)
                _kept = {name: impl for name, impl in cat_tools.items()
                         if normalize_tool_name(name) not in self.agent._excluded_tools}
                if _kept:
                    self.agent._tools_dict.update(_kept)
                    self.agent._loaded_categories.add(cat)
        logger.info(f"[ToolLoader] 初始化完成,共{len(self.agent._tools_dict)}个工具"
                    f"(拒绝清单{len(self.agent._excluded_tools)}项,白名单{len(_names)}项)")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def load_category(self, category: ToolCategory) -> bool:
        """动态加载单个分类的工具到_tools_dict

        单一权威(2026-08-05 小欧 修复):
        - _tools_dict 与 _loaded_categories 同时写入, 保证标记=已实现
        - 返回是否真正加载成功(空实现分类返回False), 供调用方跳过标记
        2026-11-27 小欧 - 拒绝清单同源过滤: 被拒工具不因动态注入回流, 全被拒时返回False不标记
        """
        cat_tools = tool_registry.get_implementations_by_category(category)
        if not cat_tools:
            logger.info(f"[ToolLoader] 分类{category.value}无可用实现, 不标记为已加载")
            return False
        _excluded = getattr(self.agent, "_excluded_tools", ())
        _names = getattr(self.agent, "_tool_names", ())   # 小欧 2026-11-28 - 白名单同源，动态灌回不得绕过
        _kept = {name: impl for name, impl in cat_tools.items()
                 if normalize_tool_name(name) not in _excluded
                 and (not _names or normalize_tool_name(name) in _names)}
        if not _kept:
            logger.info(f"[ToolLoader] 分类{category.value}工具全部在拒绝清单内, 不加载不标记")
            return False
        self.agent._tools_dict.update(_kept)
        self.agent._loaded_categories.add(category)
        logger.info(f"[ToolLoader] 动态加载分类{category.value}, {len(_kept)}个工具")
        return True
