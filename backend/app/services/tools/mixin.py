# -*- coding: utf-8 -*-
"""
ToolLoaderMixin - 工具加载混入类

位置: app/services/tools/mixin.py
小健 - 2026-04-26

使用方式:
    class FileReactAgent(ToolLoaderMixin, BaseAgent):
        pass
"""
from typing import Dict, Callable, Optional
from app.services.tools.registry import tool_registry, get_tools_from_registry_by_category, ToolCategory


class ToolLoaderMixin:
    """
    工具加载混入类
    
    用法:
        class FileReactAgent(ToolLoaderMixin, BaseAgent):
            pass
    """
    
    def _load_tools(
        self, 
        category: Optional[ToolCategory] = None
    ) -> Dict[str, Callable]:
        """
        按分类从registry加载工具
        
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
        tool_names: list
    ) -> Dict[str, Callable]:
        """按名称加载特定工具"""
        result = {}
        for name in tool_names:
            impl = tool_registry.get_implementation(name)
            if impl:
                result[name] = impl
        return result
    
    def _load_all_tools(self) -> Dict[str, Callable]:
        """加载所有已注册的工具"""
        return tool_registry.list_all_tools()