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

from typing import Dict, List, Optional, Callable, Any, Union, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


_TYPE_ORDER = ["string", "integer", "number", "boolean", "object", "array", "null"]


def _fix_schema_types(schema: Dict[str, Any]) -> Dict[str, Any]:
    """修复Pydantic生成的JSON Schema中缺失的type字段 - 小健 2026-05-06, 小沈 2026-05-08, 2026-05-13
    
    Pydantic V2对Union/Optional/Dict等复杂类型生成anyOf/oneOf，
    导致OpenAI Schema兼容的properties中缺少type字段。
    此函数遍历properties，为缺少type的字段推断并补上。
    
    【2026-05-13 小沈】不再将Union类型拼成逗号字符串（如"string,array"）。
    原因是opencode/DeepSeek等API严格校验schema，不认逗号格式。
    改为保留anyOf结构，这是标准JSON Schema，所有OpenAI兼容API都支持。
    影响：Parameter Reminder文本中Union类型显示为"any"而非"string,array"，
    不影响实际API调用（传的是input_schema原样，不是reminder文本）。
    """
    if not schema or 'properties' not in schema:
        return schema
    
    properties = schema['properties']
    for prop_name, prop_info in properties.items():
        if 'type' in prop_info:
            continue
        
        if 'anyOf' in prop_info:
            non_null_types = []
            for item in prop_info['anyOf']:
                if isinstance(item, dict) and 'type' in item:
                    t = item['type']
                    if t != 'null':
                        non_null_types.append(t)
            
            if non_null_types:
                unique_types = list(dict.fromkeys(non_null_types))
                if len(unique_types) == 1:
                    prop_info['type'] = unique_types[0]
                # 多个类型：保留anyOf结构，不合并为逗号字符串（opencode/deepseek等API不兼容逗号格式）
        
        if 'oneOf' in prop_info and 'type' not in prop_info:
            non_null_types = []
            for item in prop_info['oneOf']:
                if isinstance(item, dict) and 'type' in item:
                    t = item['type']
                    if t != 'null':
                        non_null_types.append(t)
            
            if non_null_types:
                unique_types = list(dict.fromkeys(non_null_types))
                if len(unique_types) == 1:
                    prop_info['type'] = unique_types[0]
        
        if 'type' not in prop_info and 'anyOf' not in prop_info and 'oneOf' not in prop_info:
            if '$ref' in prop_info:
                prop_info['type'] = 'object'
            elif 'allOf' in prop_info:
                prop_info['type'] = 'object'
            else:
                prop_info['type'] = 'string'
    
    return schema


class ToolCategory(Enum):
    """
    工具分类枚举 - 【2026-05-18 小沈】精简方案：13→7分类
    实际注册映射(与INTENT_TO_CATEGORY同步):
      SHELL/META工具→注册到SYSTEM, TIME→SYSTEM, ENVIRONMENT→SYSTEM,
      DATABASE→DOCUMENT, CODE_EXECUTION→SYSTEM, DATA_FORMAT→FILE
    注意: SHELL和META枚举值保留用于INTENT_TO_CATEGORY兼容, 但无工具直接注册到它们
    【2026-05-24 小沈】修正INTENT_TO_CATEGORY映射与实际注册一致
    """
    FILE = "file"
    SHELL = "shell"         # Shell命令执行 + 代码执行 (实际注册到SYSTEM)
    NETWORK = "network"     # 网络通信
    SYSTEM = "system"        # 系统信息 + 环境管理 + Shell + Meta/时间
    DESKTOP = "desktop"     # 桌面功能
    DOCUMENT = "document"      # 文档读写 + 数据库
    META = "meta"              # 元工具 + 时间日期 (实际注册到SYSTEM)


INTENT_TO_CATEGORY: Dict[str, "ToolCategory"] = {
    "file": ToolCategory.FILE,
    "shell": ToolCategory.SYSTEM,
    "network": ToolCategory.NETWORK,
    "system": ToolCategory.SYSTEM,
    "desktop": ToolCategory.DESKTOP,
    "document": ToolCategory.DOCUMENT,
    "meta": ToolCategory.SYSTEM,
    "time": ToolCategory.SYSTEM,
    "environment": ToolCategory.SYSTEM,
    "env": ToolCategory.SYSTEM,
    "database": ToolCategory.DOCUMENT,
    "code_execution": ToolCategory.SYSTEM,
    "data_format": ToolCategory.FILE,
    "data_analysis": ToolCategory.DOCUMENT,
}


def resolve_category(intent_type: str) -> Optional["ToolCategory"]:
    """意图类型→ToolCategory解析，支持新旧意图名 - 【2026-05-18 小沈】"""
    cat = INTENT_TO_CATEGORY.get(intent_type)
    if cat:
        return cat
    try:
        return ToolCategory(intent_type)
    except ValueError:
        return None


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
    expose_to_llm: bool = True
    next_actions: Dict[str, Any] = field(default_factory=dict)
    failure_hint_fn: Optional[Callable] = None
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

    def get_failure_hint(self, tool_params: Optional[dict] = None) -> str:
        """获取工具失败时的替代建议 — 小健 2026-05-24"""
        if self.failure_hint_fn:
            try:
                return self.failure_hint_fn(tool_params)
            except Exception:
                pass
        return ""


def _generate_input_schema(input_model: Optional[Type[BaseModel]], input_schema: Optional[Dict]) -> Dict:
    """从 input_model 生成 input_schema（优先于传入的 schema — 小健 2026-05-25）"""
    if input_model is None:
        return input_schema or {}
    try:
        schema = input_model.model_json_schema()
        schema = _fix_schema_types(schema)
        logger.info(f"[ToolRegistry.register] 从 Pydantic 模型生成 input_schema")
        return schema
    except Exception as e:
        logger.error(f"[ToolRegistry.register] 从 Pydantic 模型生成 Schema 失败: {e}")
        return input_schema or {}


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
    
    # 【Phase 3 小沈 2026-05-18】精简方案：7分类
    CATEGORY_ORDER = [
        ToolCategory.FILE, ToolCategory.SHELL, ToolCategory.NETWORK,
        ToolCategory.SYSTEM, ToolCategory.DESKTOP, ToolCategory.DOCUMENT,
        ToolCategory.META,
    ]

    CATEGORY_NAMES = {
        ToolCategory.FILE: "文件操作工具",
        ToolCategory.SHELL: "Shell/代码执行工具",
        ToolCategory.NETWORK: "网络通信工具",
        ToolCategory.SYSTEM: "系统/环境工具",
        ToolCategory.DESKTOP: "桌面工具",
        ToolCategory.DOCUMENT: "文档(含数据分析与数据库)工具",
        ToolCategory.META: "时间/元工具",
    }

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
        include_metadata: bool = True,
        expose_to_llm_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        列出工具
        
        Args:
            category: 按分类过滤（可选）
            include_metadata: 是否包含元数据（默认True返回dict）
            expose_to_llm_only: 是否只返回暴露给LLM的工具（默认False返回全部） - 小沈2026-05-02
        
        Returns:
            工具信息dict列表
        """
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
    
    # ===== 跨分类工具概要（2026-04-30 小沈新增）=====

    def _extract_required_params(self, input_schema: Optional[Dict]) -> List[str]:
        """
        从input_schema中提取必填参数名

        Args:
            input_schema: Pydantic模型生成的schema字典

        Returns:
            必填参数名列表（排序后）
        """
        if not input_schema:
            return []
        required = set(input_schema.get("required", []))
        return sorted(required)

    def list_all_tools(self) -> Dict[str, Callable]:
        """获取所有工具实现
        
        Returns:
            工具名到实现的映射字典
        """
        return self._implementations.copy()
    
    def get_all_tools_summary(self, priority_category: Optional['ToolCategory'] = None,
                               expose_to_llm_only: bool = True,
                               exclude_categories: Optional[set] = None) -> str:
        """获取工具概要描述（分类标题+工具名+一句话描述） - 小健 2026-05-15 重构

        【重构 小健 2026-05-15】在工具名后追加一句话描述（取description首句，约50字），
        LLM可以判断是否需要加载该分类。

        Args:
            priority_category: 优先展示的分类
            expose_to_llm_only: 是否只展示暴露给LLM的工具
            exclude_categories: 排除的分类集合

        Returns:
            格式化的工具概要字符串
        """
        lines = []
        lines.append("=== 其他可用工具（概要）===")
        lines.append("")

        from collections import defaultdict
        by_category: Dict[ToolCategory, List[str]] = defaultdict(list)
        for name, metadata in self._tools.items():
            if expose_to_llm_only and not metadata.expose_to_llm:
                continue
            if exclude_categories and metadata.category.value in exclude_categories:
                continue
            by_category[metadata.category].append((name, metadata))

        category_order = list(self.CATEGORY_ORDER)
        if priority_category and priority_category in category_order:
            category_order.remove(priority_category)
            category_order.insert(0, priority_category)

        for cat in category_order:
            if exclude_categories and cat.value in exclude_categories:
                continue
            items = by_category.get(cat, [])
            if not items:
                continue
            display_name = self.CATEGORY_NAMES.get(cat, cat.value)
            lines.append(f"【{display_name}】")
            for name, meta in sorted(items, key=lambda x: x[0]):
                # 取description首句（到第一个句号）作为一句话概要
                desc = meta.description.split("。")[0][:80]
                lines.append(f"  {name}: {desc}")
            lines.append("")

        return "\n".join(lines)

    def get_all_tools_detail(self, priority_category: Optional['ToolCategory'] = None,
                             category_filter: Optional['ToolCategory'] = None,
                             exclude_categories: Optional[set] = None,
                              expose_to_llm_only: bool = True) -> str:
        """获取工具完整描述（使用场景+示例+返回格式） - 小健 2026-05-14
        
        【修复 小健 2026-05-15】category_filter指定时不再添加"=== 可用工具列表 ==="标题，
        避免_loaded_categories多分类遍历时重复标题。

        与 get_all_tools_summary（概要版）互补，此方法输出每个工具的完整description。

        Args:
            priority_category: 优先展示的分类（排在最前）
            category_filter: 只输出指定分类的工具（None=全部）
            exclude_categories: 排除的分类集合（避免与概要重复）
            expose_to_llm_only: 是否只展示暴露给LLM的工具

        Returns:
            格式化的工具完整描述字符串
        """
        lines = []
        # category_filter时用分类名作标题，不放"=== 可用工具列表 ==="避免重复
        if category_filter:
            display = self.CATEGORY_NAMES.get(category_filter, category_filter.value)
            lines.append(f"=== {display} ===")
        else:
            lines.append("=== 可用工具列表（完整）===")
        lines.append("")

        from collections import defaultdict
        by_category: Dict[ToolCategory, List[str]] = defaultdict(list)
        for name, metadata in self._tools.items():
            if expose_to_llm_only and not metadata.expose_to_llm:
                continue
            if category_filter and metadata.category != category_filter:
                continue
            if exclude_categories and metadata.category.value in exclude_categories:
                continue
            by_category[metadata.category].append((name, metadata))

        category_order = list(self.CATEGORY_ORDER)
        if priority_category and priority_category in category_order:
            category_order.remove(priority_category)
            category_order.insert(0, priority_category)

        for cat in category_order:
            if cat not in by_category:
                continue
            items = by_category[cat]
            display_name = self.CATEGORY_NAMES.get(cat, cat.value)
            lines.append(f"【{display_name}】")
            for name, meta in sorted(items, key=lambda x: x[0]):
                lines.append(f"  {name}: {meta.description}")
            lines.append("")

        return "\n".join(lines)

    def to_openai_tools(self, category: Optional['ToolCategory'] = None) -> List[Dict]:
        """
        生成OpenAI API格式的tools定义 - 小沈 2026-05-09

        Args:
            category: 工具分类，None=全部

        Returns:
            [{"type": "function", "function": {...}}, ...]
        """
        tools = []
        for name, meta in sorted(self._tools.items(), key=lambda x: x[0]):
            if not meta.expose_to_llm:
                continue
            if category and meta.category != category:
                continue
            tools.append({
                "type": "function",
                "function": {
                    "name": meta.name,
                    "description": meta.description,
                    "parameters": meta.input_schema
                }
            })

        return tools

    @staticmethod
    def _format_default(val) -> str:
        """将 Pydantic 默认值格式化为字符串，跳过 None - 小沈 2026-05-09"""
        if val is None:
            return ""
        if isinstance(val, str):
            return "default=" + val
        if isinstance(val, bool):
            return "default=" + ("true" if val else "false")
        if isinstance(val, (int, float)):
            return "default=" + str(val)
        return ""

    def generate_param_reminder(self, category: Optional['ToolCategory'] = None, style: str = "code") -> str:
        """
        从 input_schema 自动生成 Parameter Reminder 文本 - 小沈 2026-05-09

        参数信息完全来自 Pydantic 模型：
        - 参数名：properties 的 key
        - 参数类型：properties[field].type
        - 必填/可选：是否在 required 数组中
        - 默认值：properties[field].default（跳过 None）

        Args:
            category: 工具分类，None=全部
            style: "code"=函数签名风格(推荐), "text"=自然语言风格(兼容)
        """
        TYPE_MAP = {"integer": "int", "number": "number", "string": "str", "boolean": "bool", "object": "dict", "array": "list"}
        header = "Parameter Reminder (auto-generated from Pydantic):" if style == "text" else "Available Functions (auto-generated):"
        lines = [header, ""]
        for name, meta in sorted(self._tools.items(), key=lambda x: x[0]):
            if not meta.expose_to_llm:
                continue
            if category and meta.category != category:
                continue
            schema = meta.input_schema
            if not schema or "properties" not in schema:
                continue
            
            required_set = set(schema.get("required", []))
            param_parts = []
            for pname, pinfo in schema.get("properties", {}).items():
                ptype = pinfo.get("type")
                if ptype is None:
                    if "anyOf" in pinfo:
                        type_set = set()
                        for item in pinfo["anyOf"]:
                            if isinstance(item, dict) and "type" in item and item["type"] != "null":
                                type_set.add(item["type"])
                        ptype = "/".join(sorted(type_set)) if type_set else "any"
                    elif "oneOf" in pinfo:
                        type_set = set()
                        for item in pinfo["oneOf"]:
                            if isinstance(item, dict) and "type" in item and item["type"] != "null":
                                type_set.add(item["type"])
                        ptype = "/".join(sorted(type_set)) if type_set else "any"
                    else:
                        ptype = "any"
                req_str = "required" if pname in required_set else "optional"
                default_str = self._format_default(pinfo.get("default"))

                if style == "code":
                    short_type = "/".join(TYPE_MAP.get(t.strip(), t.strip()) for t in ptype.split("/"))
                    optional_mark = "" if pname in required_set else "?"
                    default_expr = ""
                    if default_str:
                        default_expr = "=" + default_str.split("=", 1)[1]
                    param_parts.append(f"{pname}{optional_mark}: {short_type}{default_expr}")
                else:
                    if default_str:
                        param_parts.append("{}({}, {}, {})".format(pname, req_str, ptype, default_str))
                    else:
                        param_parts.append("{}({}, {})".format(pname, req_str, ptype))
            
            if param_parts:
                if style == "code":
                    lines.append(f"def {name}({', '.join(param_parts)})")
                else:
                    lines.append("- " + name + ": " + ", ".join(param_parts))
        
        return "\n".join(lines)

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

    def get_tool_meta(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具元数据（dict格式，兼容旧接口）"""
        meta = self._tools.get(name)
        if meta is None:
            return None
        example_str = ""
        if meta.examples:
            params = meta.examples[0]
            def fmt_val(v):
                if isinstance(v, str):
                    return f'"{v}"'
                return repr(v)
            parts = [f'{k}={fmt_val(v)}' for k, v in params.items()]
            example_str = f'{name}({", ".join(parts)})'
        return {
            "description": meta.description,
            "parameters": meta.input_schema,
            "returns": meta.output_schema,
            "example": example_str,
            "when_to_use": "",
        }


# 全局工具注册表实例
# 【小健 2026-04-29】后续新增所有工具分类（time/shell/network/env/system/database/desktop）的register文件，必须按此规范使用input_model参数注册，禁止旧的非规范方式
tool_registry = ToolRegistry()


# 装饰器版本（支持 Pydantic 模型）
def register_tool(
    name: Optional[str] = None,
    description: str = "",
    category: ToolCategory = ToolCategory.FILE,
    version: str = "1.0.0",
    dependencies: Optional[List[str]] = None,
    # 【小健 2026-04-29】装饰器input_model参数：必须传入Pydantic模型类，禁止手动传input_schema（除非无对应Pydantic模型）
    input_model: Optional[Type[BaseModel]] = None,
    input_schema: Optional[Dict] = None,
    output_schema: Optional[Dict] = None,
    examples: Optional[List[Dict]] = None,
    expose_to_llm: bool = True,
):
    """
    工具注册装饰器
    
    【2026-04-29 小沈更新】支持 Pydantic 模型注册
    【小健 2026-04-29】强制要求：新增工具必须使用input_model参数，禁止旧的非规范注册方式
    【小健 2026-04-29】后续新增工具类型（time/shell/network等）也必须遵守此规范
    
    用法:
        # 方式1：使用 Pydantic 模型（推荐）
        @register_tool(
            name="list_directory",
            description="列出目录内容",
            category=ToolCategory.FILE,
            input_model=ListDirectoryInput
        )
        async def list_directory(params): ...
        
        # 方式2：使用字典（兼容旧代码）
        @register_tool(
            name="list_directory",
            description="列出目录内容",
            category=ToolCategory.FILE,
            input_schema={"type": "object", "properties": {...}}
        )
        async def list_directory(params): ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # 【小健 2026-04-29】强制传入input_model参数，禁止手动编写input_schema，符合文档5.1要求
        # 注册工具（支持 input_model）
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
    从tool_registry获取所有工具实现函数

    Returns:
        {工具名: 工具函数} 格式
    """
    # 【P0-B1修复 小健小沈 2026-05-26】list_tools()返回格式可能为[str]或[dict]，需适配
    tools_list = tool_registry.list_tools()
    if tools_list and isinstance(tools_list[0], dict):
        tool_names = [t["name"] for t in tools_list if "name" in t]
    else:
        tool_names = tools_list
    return {name: tool_registry.get_implementation(name)
            for name in tool_names}


def get_tools_from_registry_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """
    按分类从registry获取工具（别名: get_tools_dict_by_category）
    参考: 文档5.3节+7.6节完整代码
    
    Args:
        category: 工具分类
    
    Returns:
        {工具名: 工具函数} 格式
    """
    # Get tool list - handle both old and new return formats
    tools_list = tool_registry.list_tools(category=category, include_metadata=False)
    
    # If tools_list is list of dicts (new format), extract names
    if tools_list and isinstance(tools_list[0], dict):
        tool_names = [t["name"] for t in tools_list if "name" in t]
    else:
        tool_names = tools_list
    
    # Get implementations
    result = {}
    for name in tool_names:
        impl = tool_registry.get_implementation(name)
        if impl:
            result[name] = impl
    return result


# 别名兼容性
get_tools_dict_by_category = get_tools_from_registry_by_category


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


# 已知file工具名列表（统一命名）
_FILE_TOOL_NAMES = [
    "read_file", "write_text_file", "read_media_file", "edit_file",
    "list_directory", "search_files", "grep_file_content", "rename_file",
    "archive_tool", "file_operation", "data_file_format"
]
