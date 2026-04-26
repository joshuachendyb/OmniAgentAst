# -*- coding: utf-8 -*-
"""
工具注册表模块 - 统一入口

【架构规范】2026-04-26 小沈

================================================================================
一、总体架构
================================================================================
- registry.py: 总注册表，统一入口，所有工具通过 @register_tool 装饰器注册到这里
- 各分类目录: {category}_register.py（注册点）+ {category}_tools.py（实现）

================================================================================
二、新增工具流程
================================================================================
1. 在对应分类的 {category}_tools.py 中编写实现函数
2. 在对应分类的 {category}_register.py 中使用 @register_tool 装饰器注册
3. 在分类的 __init__.py 中导入注册模块（触发注册）

示例：
    # file/file_register.py
    from app.services.tools.registry import register_tool, ToolCategory
    from app.services.tools.file.file_tools import read_file, write_file
    
    @register_tool(name="read_file", description="读取文件", category=ToolCategory.FILE)
    def read_file(...): pass

================================================================================
三、目录组织规范
================================================================================
| 分类     | 目录    | 注册文件         | 实现文件         |
|----------|---------|------------------|------------------|
| 文件操作 | file/   | file_register.py | file_tools.py    |
| 时间日期 | time/   | time_register.py | time_tools.py    |
| Shell命令| shell/ | shell_register.py| shell_tools.py   |
| 网络通信 | network/| network_register.py| network_tools.py|
| 环境变量 | env/   | env_register.py  | env_tools.py     |
| 系统信息 | system/ | system_register.py| system_tools.py  |
| 数据库   | database/| database_register.py|database_tools.py|
| 桌面功能 | desktop/| desktop_register.py| desktop_tools.py|

================================================================================
四、命名规范
================================================================================
- 注册装饰器: @register_tool（来自 registry.py）
- 注册函数别名: {分类}tool（可选，如 filetool = tool_registry）
- 实现文件: {分类}_tools.py
- 注册文件: {分类}_register.py
- 模式文件: {分类}_schema.py（用于Pydantic模型）

================================================================================
五、必须遵守的规则
================================================================================
1. 工具必须注册到 registry.py 的 tool_registry
2. 各分类只负责实现，注册在 __init__.py 导入时自动触发
3. 文件名必须具体，不能用笼统名称如 tools.py
4. 空目录保留，用于未来扩展
5. 分类枚举必须使用 ToolCategory 枚举类

================================================================================
六、TODO - 待实现分类
================================================================================
| 分类     | 状态  | 工具数量 | 说明                    |
|----------|-------|----------|-------------------------|
| TIME     | 待创建 | 9个      | 时间/日期工具           |
| SHELL    | 待创建 | 3个      | Shell命令执行           |
| NETWORK  | 待创建 | 2个      | 网络通信                |
| ENV      | 待创建 | 2个      | 环境变量                |
| SYSTEM   | 待创建 | 1个      | 系统信息                |
| DATABASE | 待创建 | 3个      | 数据库访问              |
| DESKTOP  | 待创建 | 0个      | 桌面功能（保留扩展）    |

创建时间: 2026-04-19 08:20:00
更新时间: 2026-04-26 10:40:00
更新人: 小沈
"""

from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """
    工具分类枚举
    
    【更新】2026-04-26 小沈
    - 原有: FILE, DATABASE, NETWORK, SYSTEM, DESKTOP
    - 新增: TIME, SHELL, ENV
    """
    FILE = "file"
    TIME = "time"           # 时间/日期
    SHELL = "shell"         # Shell命令执行
    NETWORK = "network"     # 网络通信
    ENV = "env"             # 环境变量
    SYSTEM = "system"        # 系统信息
    DATABASE = "database"   # 数据库访问
    DESKTOP = "desktop"     # 桌面功能


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.examples is None:
            self.examples = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at


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
        input_schema: Optional[Dict] = None,
        output_schema: Optional[Dict] = None,
        examples: Optional[List[Dict]] = None
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
            input_schema: 输入参数Schema
            output_schema: 输出结果Schema
            examples: 使用示例
        
        Returns:
            {"status": "success"} or {"status": "error", "error": "..."}
        
        Raises:
            ValueError: 如果工具已注册（首次注册时）
        """
        # 允许重复注册（更新模式）
        if name in self._tools:
            # 更新已有工具
            metadata = self._tools[name]
            metadata.description = description
            metadata.version = version
            metadata.updated_at = datetime.now()
            self._implementations[name] = implementation
            logger.info(f"Tool updated: {name} (version: {version})")
            return {"status": "success"}
        
        # 验证依赖关系
        if dependencies:
            missing = [dep for dep in dependencies if dep not in self._tools]
            if missing:
                raise ValueError(f"Missing dependencies: {missing}")
        
        # 创建工具元数据
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            version=version,
            dependencies=dependencies or [],
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            examples=examples or []
        )
        
        # 注册工具
        self._tools[name] = metadata
        self._implementations[name] = implementation
        
        # 更新分类索引
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        
        # 更新工具更新时间
        metadata.updated_at = datetime.now()
        
        logger.info(f"Tool registered: {name} (category: {category.value})")
        
        return {"status": "success"}
    
    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具元数据（返回dict格式）
        
        Args:
            name: 工具名称
        
        Returns:
            dict: 工具信息dict或None
        """
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
        """
        获取工具元数据（返回dataclass）
        
        Args:
            name: 工具名称
        
        Returns:
            ToolMetadata: 工具元数据，如果不存在则返回None
        """
        return self._tools.get(name)
    
    def get_implementation(self, name: str) -> Optional[Callable]:
        """
        获取工具实现函数
        
        Args:
            name: 工具名称
        
        Returns:
            工具实现函数，如果不存在则返回None
        """
        return self._implementations.get(name)
    
    def get_exact_implementation(self, name: str) -> Optional[Callable]:
        """
        获取工具实现函数（使用精确名称匹配）
        
        Args:
            name: 工具名称
        
        Returns:
            工具实现函数，如果不存在则返回None
        """
        return self._implementations.get(name)
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        列出工具
        
        Args:
            category: 按分类过滤（可选）
            include_metadata: 是否包含元数据（默认True返回dict）
        
        Returns:
            工具信息dict列表
        """
        if category:
            tool_names = self._categories.get(category, [])
        else:
            tool_names = list(self._tools.keys())
        
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
        """
        注销工具
        
        Args:
            name: 工具名称
        
        Returns:
            dict: {"status": "success"} or {"status": "error", "error": "..."}
        """
        if name not in self._tools:
            return {"status": "error", "error": f"Tool '{name}' not found"}
        
        metadata = self._tools[name]
        
        # 从分类索引中移除
        category_tools = self._categories.get(metadata.category, [])
        if name in category_tools:
            category_tools.remove(name)
        
        # 移除工具
        del self._tools[name]
        del self._implementations[name]
        
        logger.info(f"Tool unregistered: {name}")
        return {"status": "success"}
    
    def __len__(self) -> int:
        """返回已注册工具数量"""
        return len(self._tools)


# 全局工具注册表实例
tool_registry = ToolRegistry()


# 装饰器版本（兼容现有file_tools.py）
def register_tool(
    name: Optional[str] = None,
    description: str = "",
    category: ToolCategory = ToolCategory.FILE,
    version: str = "1.0.0",
    dependencies: Optional[List[str]] = None,
    input_schema: Optional[Dict] = None,
    output_schema: Optional[Dict] = None,
    examples: Optional[List[Dict]] = None
):
    """
    工具注册装饰器
    
    用法:
        @register_tool(
            name="list_directory",
            description="列出目录内容",
            category=ToolCategory.FILE
        )
        async def list_directory(params):
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # 自动从函数签名生成输入Schema
        if 'input_schema' not in locals():  # 修复未定义问题
            input_schema = None
        if input_schema is None:
            input_schema = {}
        
        # 注册工具
        tool_registry.register(
            name=tool_name,
            description=description or func.__doc__ or "",
            category=category,
            implementation=func,
            version=version,
            dependencies=dependencies,
            input_schema=input_schema,
            output_schema=output_schema,
            examples=examples
        )
        
        return func
    
    return decorator


# 兼容层：保留原有接口
def get_registered_tools() -> List[Dict[str, Any]]:
    """获取已注册的工具列表（兼容旧接口）"""
    return [
        {
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category.value,
            "version": metadata.version,
        }
        for metadata in tool_registry.list_tools(include_metadata=True)
    ]


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """获取工具定义（兼容旧接口）"""
    metadata = tool_registry.get_tool(name)
    if not metadata:
        return None
    
    return {
        "name": metadata.name,
        "description": metadata.description,
        "category": metadata.category.value,
        "version": metadata.version,
        "input_schema": metadata.input_schema,
        "examples": metadata.examples,
    }


def get_tools_dict() -> Dict[str, Callable]:
    """
    获取工具函数字典（兼容旧接口，供ToolExecutor使用）
    
    Returns:
        {工具名: 工具函数} 格式
    """
    return tool_registry._implementations


def get_implementations_from_registry() -> Dict[str, Callable]:
    """
    【M5新增】从tool_registry获取所有工具实现函数
    
    如果tool_registry为空，自动从file_tools._TOOL_REGISTRY同步
    
    Returns:
        {工具名: 工具函数} 格式
    """
    # 如果registry为空，从旧_TOOL_REGISTRY同步
    if not tool_registry._implementations:
        _sync_from_old_registry()
    
    return tool_registry._implementations


def _sync_from_old_registry():
    """占位函数（旧同步逻辑已废弃）"""
    pass  # 不再需要同步，已迁移到各register.py


def get_tools_dict_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """
    按分类获取工具函数字典
    
    Args:
        category: 工具分类
    
    Returns:
        {工具名: 工具函数} 格式
    """
    tools = tool_registry.list_tools(category=category, include_metadata=True)
    result = {}
    for tool_info in tools:
        name = tool_info["name"]
        impl = tool_registry.get_implementation(name)
        if impl:
            result[name] = impl
    return result


def get_tools_from_file_registry() -> Dict[str, Callable]:
    """
    从tool_registry获取file工具
    
    Returns:
        {工具名: 工具函数} 格式
    """
    # 触发 file_register 注册（确保注册已执行）
    from app.services.tools.file import file_register
    
    # 直接使用全局 tool_registry 实例
    result = {}
    for name in _FILE_TOOL_NAMES:  # 已知工具名列表
        impl = tool_registry.get_exact_implementation(name)
        if impl:
            result[name] = impl
    return result


# 已知file工具名列表（从file_register同步）
_FILE_TOOL_NAMES = [
    "read_file", "write_file", "list_directory", "delete_file", "move_file",
    "search_file_content", "search_files_by_name", "generate_report", "copy_file",
    "create_directory", "get_file_info", "compare_files", "batch_rename",
    "compress_files", "file_monitor", "file_statistics", "file_checksum"
]
