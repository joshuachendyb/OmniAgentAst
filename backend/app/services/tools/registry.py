# -*- coding: utf-8 -*-
"""
工具注册表模块 - 统一入口

【架构规范】2026-04-26 小沈

拆分自 884行 → ~250行 — 小沈 2026-05-29
移出内容: ToolCategory/ToolMetadata → tool_types.py, Schema处理 → schema_utils.py,
         查询函数 → tool_queries.py, 格式转换 → tool_format.py
"""

from typing import Dict, List, Optional, Callable, Any, Type
from datetime import datetime
from pydantic import BaseModel
from app.services.tools.tool_types import ToolCategory, ToolMetadata
from app.services.tools.schema_utils import _generate_input_schema
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def _update_tool_metadata(metadata: ToolMetadata, **kwargs) -> None:
    """更新工具元数据的可选字段 — 小健 2026-05-25"""
    for key, value in kwargs.items():
        if value is not None:
            setattr(metadata, key, value)
    metadata.updated_at = datetime.now()


class ToolRegistry:
    """
    类型安全的工具注册表
    
    功能:
    - 注册工具 (register)
    - 获取工具 (get_tool, get_implementation)
    - 列出工具 (list_tools)
    - 注销工具 (unregister)
    
    使用方式:
        registry = ToolRegistry()
        registry.register(name="xxx", description="...", category=ToolCategory.FILE, implementation=func)
    """

    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._categories: Dict[ToolCategory, List[str]] = {}
        self._implementations: Dict[str, Callable] = {}
    
    def register(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        implementation: Callable,
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        input_model: Optional[Type[BaseModel]] = None,
        input_schema: Optional[Dict] = None,
        output_schema: Optional[Dict] = None,
        examples: Optional[List[Dict]] = None,
        expose_to_llm: bool = True,
        next_actions: Optional[Dict[str, Any]] = None,
        failure_hint_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        注册工具
        
        Args:
            name: 工具名称
            description: 工具描述
            category: 工具分类
            implementation: 工具实现函数
            version: 版本号
            dependencies: 依赖的其他工具
            input_model: Pydantic 模型类，自动生成 input_schema
            input_schema: 输入参数Schema（当没有 input_model 时使用）
            output_schema: 输出结果Schema
            examples: 使用示例
            expose_to_llm: 是否暴露给LLM（默认True），为False时工具仅作为内部辅助函数不发送给LLM - 小沈2026-05-02
        
        Returns:
            {"status": "success"} or {"status": "error", "error": "..."}
        
        Raises:
            ValueError: 如果工具已注册（首次注册时）
        """
        input_schema = _generate_input_schema(input_model, input_schema)

        # 更新路径
        if name in self._tools:
            _update_tool_metadata(self._tools[name],
                description=description, version=version, category=category,
                input_schema=input_schema, output_schema=output_schema, examples=examples)
            self._implementations[name] = implementation
            return {"status": "success"}

        # 依赖验证
        if dependencies:
            missing = [dep for dep in dependencies if dep not in self._tools]
            if missing:
                raise ValueError(f"Missing dependencies: {missing}")

        # 新建路径
        metadata = ToolMetadata(
            name=name, description=description, category=category, version=version,
            dependencies=dependencies or [], input_schema=input_schema or {},
            output_schema=output_schema or {}, examples=examples or [],
            expose_to_llm=expose_to_llm, next_actions=next_actions or {},
            failure_hint_fn=failure_hint_fn,
        )
        self._tools[name] = metadata
        self._implementations[name] = implementation

        self._categories.setdefault(category, [])
        if name not in self._categories[category]:
            self._categories[category].append(name)

        metadata.updated_at = datetime.now()
        logger.info(f"Tool registered: {name} (category: {category.value})")
        return {"status": "success"}
    
    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具元数据（返回dict格式）"""
        metadata = self._tools.get(name)
        if metadata is None:
            return None
        return {
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category.value,
            "version": metadata.version,
            "implementation": self._implementations.get(name),
        }
    
    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据（返回dataclass）"""
        return self._tools.get(name)
    
    def get_implementation(self, name: str) -> Optional[Callable]:
        """获取工具实现函数"""
        return self._implementations.get(name)
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        include_metadata: bool = True,
        expose_to_llm_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """列出工具"""
        if category:
            tool_names = self._categories.get(category, [])
        else:
            tool_names = list(self._tools.keys())
        
        if expose_to_llm_only:
            tool_names = [name for name in tool_names if self._tools[name].expose_to_llm]
        
        return [
            {
                "name": self._tools[name].name,
                "description": self._tools[name].description,
                "category": self._tools[name].category.value,
                "version": self._tools[name].version,
            }
            for name in tool_names
        ]
    
    def unregister(self, name: str) -> Dict[str, Any]:
        """注销工具"""
        if name not in self._tools:
            return {"status": "error", "error": f"Tool '{name}' not found"}
        
        metadata = self._tools[name]
        category_tools = self._categories.get(metadata.category, [])
        if name in category_tools:
            category_tools.remove(name)
        
        del self._tools[name]
        del self._implementations[name]
        
        logger.info(f"Tool unregistered: {name}")
        return {"status": "success"}
    
    def list_all_tools(self) -> Dict[str, Callable]:
        """获取所有工具实现"""
        return self._implementations.copy()

    def __len__(self) -> int:
        """返回已注册工具数量"""
        return len(self._tools)

    def get_categories(self) -> Dict[ToolCategory, List[str]]:
        """返回分类→工具名列表映射（copy防外部修改）— 小沈 2026-05-25"""
        return {k: list(v) for k, v in self._categories.items()}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """获取全局工具注册表单例实例"""
        return tool_registry


# 全局工具注册表实例
tool_registry = ToolRegistry()


# 装饰器版本（支持 Pydantic 模型）
def register_tool(
    name: Optional[str] = None,
    description: str = "",
    category: ToolCategory = ToolCategory.FILE,
    version: str = "1.0.0",
    dependencies: Optional[List[str]] = None,
    input_model: Optional[Type[BaseModel]] = None,
    input_schema: Optional[Dict] = None,
    output_schema: Optional[Dict] = None,
    examples: Optional[List[Dict]] = None,
    expose_to_llm: bool = True,
):
    """
    工具注册装饰器
    
    用法:
        @register_tool(
            name="list_directory",
            description="列出目录内容",
            category=ToolCategory.FILE,
            input_model=ListDirectoryInput
        )
        async def list_directory(params): ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_registry.register(
            name=tool_name,
            description=description or func.__doc__ or "",
            category=category,
            implementation=func,
            version=version,
            dependencies=dependencies,
            input_model=input_model,
            input_schema=input_schema,
            output_schema=output_schema,
            examples=examples,
            expose_to_llm=expose_to_llm,
        )
        return func
    
    return decorator
