# -*- coding: utf-8 -*-
"""
ToolLoaderMixin - 工具加载混入类

位置: app/services/tools/mixin.py
参考: 文档5.2节+7.2节完整代码
小健 - 2026-04-26

【修复 2026-04-30 小沈】将 _load_tools 改名为 load_tools_by_category，
消除与 BaseAgent._load_tools 的 MRO 遮蔽冲突。
原 _load_tools 名冲突导致 BaseAgent._load_tools 在子类中成为死代码。

使用方式:
    class FileReactAgent(ToolLoaderMixin, BaseAgent):
        def __init__(self, ...):
            super().__init__(...)
            # BaseAgent.__init__ 中 self._load_tools() 正常执行
            # 如需覆盖工具，可再调用:
            self._tools_dict = self.load_tools_by_category(self.tool_category)
"""
from typing import Dict, Callable, Optional, List
from app.services.tools.registry import tool_registry
from app.services.tools.tool_queries import get_tools_from_registry_by_category
from app.services.tools.tool_types import ToolCategory


class ToolLoaderMixin:
    """
    工具加载混入类
    
    【修复 2026-04-30 小沈】方法名改为 load_tools_by_category，避免与 BaseAgent._load_tools 冲突
    
    用法:
        class FileReactAgent(ToolLoaderMixin, BaseAgent):
            pass
    """
    
    def load_tools_by_category(
        self, 
        category: Optional[ToolCategory] = None
    ) -> Dict[str, Callable]:
        """
        从registry按分类加载工具
        
        【修复 2026-04-30 小沈】从 _load_tools 改名，消除MRO遮蔽
        
        Args:
            category: 工具分类
            
        Returns:
            {工具名: 工具函数}
        """
        if not category:
            return {}
        
        return get_tools_from_registry_by_category(category)
    
    def _load_tools_by_names(
        self, 
        tool_names: List[str]
    ) -> Dict[str, Callable]:
        """
        按名称加载特定工具
        
        Args:
            tool_names: 工具名称列表
        
        Returns:
            {工具名: 工具函数}
        """
        result = {}
        for name in tool_names:
            impl = tool_registry.get_implementation(name)
            if impl:
                result[name] = impl
        return result
    
    def _load_all_tools(self) -> Dict[str, Callable]:
        """加载所有已注册的工具"""
        return tool_registry.list_all_tools()
