
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-25 - 小欧 - ensure_tools_registered加即时重试(3次,500ms间隔),应对并发写导致的瞬态文件损坏
# 2026-07-25 - 小欧 - 错误日志加filename:lineno上下文(欧阳建议)
# 2026-08-07 - 小欧 - get_tool工具名别名归一化: LLM常生成变体名(write_text等), 经tools_alias_mapper.normalize_tool_name映射到注册名(writetext), 防"工具未注册"误拦截(com-test 03暴露)
"""
工具注册表模块 - 统一入口

【架构规范】2026-04-26 小沈

拆分自 884行 → ~250行 — 小沈 2026-05-29
移出内容: ToolCategory/ToolMetadata → tool_types.py, Schema处理 → schema_utils.py,
         查询函数 → tool_queries.py, 格式转换 → tool_description.py
"""

from typing import Dict, List, Optional, Callable, Any, Type, Set, Union
from pydantic import BaseModel
from app.tools.tool_types import ToolCategory, ToolMetadata
from app.tools.schema_utils import _generate_input_schema
from app.tools.tool_description import to_openai_tools, generate_param_reminder
from app.tools.tools_alias_mapper import normalize_tool_name
from app.logger import setup_logger
from app.utils.dependency import ensure_dependency
from app.tools.tool_constants import CATEGORY_MODULES

logger = setup_logger(__name__)

# 懒加载注册状态跟踪（从 lazy_loader.py 迁入）
_registered_categories: set = set()


def _update_tool_metadata(metadata: ToolMetadata, **kwargs) -> None:
    """更新工具元数据的可选字段 — 小健 2026-05-25"""
    for key, value in kwargs.items():
        if value is not None:
            setattr(metadata, key, value)


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
    
    def _check_dependencies(self, dependencies: List[Union[str, Dict[str, Any]]], tool_name: str) -> bool:
        """检查并安装工具依赖 — 小健 2026-06-18
        
        Args:
            dependencies: 依赖包列表，可以是字符串或字典
                字符串格式: 'pandas' 或 'httpx==0.26.0'
                字典格式: {
                    'import_name': 'win10toast', 
                    'pip_package': 'win10toast', 
                    'version': '==0.10.0',
                    'pre_install': ['setuptools<70']
                }
            tool_name: 工具名称，用于日志记录
        
        Returns:
            bool: True=所有依赖都可用，False=有依赖安装失败
        """
        if not dependencies:
            return True
        
        all_available = True
        for dep in dependencies:
            if isinstance(dep, str):
                # 简单字符串格式，可能包含版本号
                if "==" in dep:
                    # 格式: 'httpx==0.26.0'
                    parts = dep.split("==")
                    if len(parts) == 2:
                        import_name = parts[0]
                        version = f"=={parts[1]}"
                        if not ensure_dependency(import_name, version=version):
                            logger.warning(f"[ToolRegistry] 工具 '{tool_name}' 依赖 '{dep}' 安装失败，工具可能不可用")
                            all_available = False
                    else:
                        logger.error(f"[ToolRegistry] 工具 '{tool_name}' 依赖格式错误: {dep}")
                        all_available = False
                else:
                    # 格式: 'pandas' (无版本号)
                    if not ensure_dependency(dep):
                        logger.warning(f"[ToolRegistry] 工具 '{tool_name}' 依赖 '{dep}' 安装失败，工具可能不可用")
                        all_available = False
            elif isinstance(dep, dict):
                # 字典格式，支持完整参数
                import_name = dep.get('import_name', dep.get('pip_package', ''))
                pip_package = dep.get('pip_package', import_name)
                version = dep.get('version')
                pre_install = dep.get('pre_install')
                
                if not import_name:
                    logger.error(f"[ToolRegistry] 工具 '{tool_name}' 依赖配置错误: {dep}")
                    all_available = False
                    continue
                
                if not ensure_dependency(import_name, pip_package, version, pre_install):
                    logger.warning(f"[ToolRegistry] 工具 '{tool_name}' 依赖 '{import_name}{version if version else ''}' 安装失败，工具可能不可用")
                    all_available = False
            else:
                logger.error(f"[ToolRegistry] 工具 '{tool_name}' 依赖格式错误: {dep}")
                all_available = False
        
        return all_available
    
    def register(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        implementation: Callable,
        version: str = "1.0.0",
        input_model: Optional[Type[BaseModel]] = None,
        input_schema: Optional[Dict] = None,
        examples: Optional[List[Dict]] = None,
        expose_to_llm: bool = True,
        failure_hint_fn: Optional[Callable] = None,
        needs_confirmation: bool = False,
        action_confirmation: Optional[Dict[str, bool]] = None,
        check_fn: Optional[Callable] = None,
        dependencies: Optional[List[Union[str, Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        注册工具（单一入口，委托给私有方法）
        
        【修复P0-5 2026-06-08 小沈】拆分为私有方法，遵守SRP原则
        【2026-06-16 小沈】用二元安全参数替代5级枚举
        【2026-06-18 小健】添加依赖管理参数
        """
        input_schema = _generate_input_schema(input_model, input_schema)
        
        # 检查并安装依赖
        deps = dependencies or []
        self._check_dependencies(deps, name)
        
        # 职责1：更新已存在工具
        if name in self._tools:
            return self._update_existing_tool(
                name, description, category, implementation, 
                input_schema, examples, version, deps,
                expose_to_llm, failure_hint_fn,
                needs_confirmation, action_confirmation, check_fn,
            )
        
        # 职责2：注册新工具
        return self._register_new_tool(
            name, description, category, implementation, 
            input_schema, examples, version, 
            expose_to_llm, failure_hint_fn,
            needs_confirmation, action_confirmation, check_fn, deps
        )
    
    def _update_existing_tool(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        implementation: Callable,
        input_schema: Optional[Dict],
        examples: Optional[List[Dict]],
        version: str,
        dependencies: List[Union[str, Dict[str, Any]]],
        expose_to_llm: bool = True,
        failure_hint_fn: Optional[Callable] = None,
        needs_confirmation: bool = False,
        action_confirmation: Optional[Dict[str, bool]] = None,
        check_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """更新已注册工具 — chendyg 2026-06-26 P1-25/26修复: 补全所有字段更新和分类索引"""
        _update_tool_metadata(
            self._tools[name],
            description=description,
            version=version,
            category=category,
            input_schema=input_schema,
            examples=examples,
            dependencies=dependencies,
            expose_to_llm=expose_to_llm,
            failure_hint_fn=failure_hint_fn,
            needs_confirmation=needs_confirmation,
            action_confirmation=action_confirmation,
            check_fn=check_fn,
        )
        self._implementations[name] = implementation
        # 【P1-26修复】更新分类索引(类别可能变更) — chendyg 2026-06-26
        self._update_category_index(category, name)
        return {"status": "success"}
    
    def _register_new_tool(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        implementation: Callable,
        input_schema: Optional[Dict],
        examples: Optional[List[Dict]],
        version: str,
        expose_to_llm: bool,
        failure_hint_fn: Optional[Callable],
        needs_confirmation: bool = False,
        action_confirmation: Optional[Dict[str, bool]] = None,
        check_fn: Optional[Callable] = None,
        dependencies: List[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """注册新工具"""
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            version=version,
            input_schema=input_schema or {},
            examples=examples or [],
            expose_to_llm=expose_to_llm,
            failure_hint_fn=failure_hint_fn,
            needs_confirmation=needs_confirmation,
            action_confirmation=action_confirmation,
            check_fn=check_fn,
            dependencies=dependencies or [],
        )
        self._tools[name] = metadata
        self._implementations[name] = implementation
        self._update_category_index(category, name)
        logger.debug(f"Tool registered: {name} (category: {category.value}, needs_confirmation: {needs_confirmation}, dependencies: {dependencies})")
        return {"status": "success"}
    
    def _update_category_index(self, category: ToolCategory, name: str) -> None:
        """更新分类索引"""
        self._categories.setdefault(category, [])
        if name not in self._categories[category]:
            self._categories[category].append(name)
    

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据(返回dataclass)
        2026-08-07 小欧: 工具名别名归一化——LLM常生成变体名(write_text等),
        精确匹配失败时经 tools_alias_mapper.normalize_tool_name 映射到注册名(writetext),
        防止"工具未注册"误拦截(com-test 03暴露)。
        """
        if not isinstance(name, str) or not name:
            return None
        tool = self._tools.get(name)
        if tool is not None:
            return tool
        return self._tools.get(normalize_tool_name(name))
    
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
    
    def get_implementations_by_category(self, category: ToolCategory) -> Dict[str, Callable]:
        """按分类一次遍历获取 {name: implementation}，消除N+1查询 — 小沈 2026-06-08"""
        tool_names = self._categories.get(category, [])
        return {name: self._implementations[name] for name in tool_names if name in self._implementations}

    def __len__(self) -> int:
        """返回已注册工具数量"""
        return len(self._tools)

    def get_categories(self) -> Dict[ToolCategory, List[str]]:
        """返回分类→工具名列表映射(copy防外部修改)— 小沈 2026-05-25"""
        return {k: list(v) for k, v in self._categories.items()}

    def to_openai_tools(self, categories: Optional[Set[ToolCategory]] = None,
                        tool_names: Optional[Set[str]] = None) -> list:
        """生成OpenAI API格式的tools定义 — 委托给tool_description.to_openai_tools — 小沈 2026-06-09"""
        return to_openai_tools(self, categories=categories, tool_names=tool_names)

    def generate_param_reminder(self, category: Optional[ToolCategory] = None, style: str = "code") -> str:
        """自动生成Parameter Reminder — 委托给tool_description.generate_param_reminder — 小沈 2026-06-09"""
        return generate_param_reminder(self, category=category, style=style)


# 全局工具注册表实例
tool_registry = ToolRegistry()


# 装饰器版本(支持 Pydantic 模型)
def register_tool(
    name: Optional[str] = None,
    description: str = "",
    category: ToolCategory = ToolCategory.FILE,
    version: str = "1.0.0",
    input_model: Optional[Type[BaseModel]] = None,
    input_schema: Optional[Dict] = None,
    examples: Optional[List[Dict]] = None,
    expose_to_llm: bool = True,
    needs_confirmation: bool = False,
    action_confirmation: Optional[Dict[str, bool]] = None,
    check_fn: Optional[Callable] = None,
    dependencies: Optional[List[Union[str, Dict[str, Any]]]] = None,
):
    """
    工具注册装饰器
    
    用法:
        @register_tool(
            name="list_directory",
            description="列出目录内容",
            category=ToolCategory.FILE,
            input_model=ListDirectoryInput,
            dependencies=["pandas", "matplotlib"]  # 可选依赖列表
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
            input_model=input_model,
            input_schema=input_schema,
            examples=examples,
            expose_to_llm=expose_to_llm,
            needs_confirmation=needs_confirmation,
            action_confirmation=action_confirmation,
            check_fn=check_fn,
            dependencies=dependencies,
        )
        return func
    
    return decorator


# ============================================================
# 懒加载注册（从 lazy_loader.py 迁入）
# ============================================================

def _import_and_register(module_path: str, register_func_name: str) -> None:
    """导入模块并调用注册函数 — 小健 2026-05-14; 小沈 2026-06-17 简化"""
    module = __import__(module_path, fromlist=[register_func_name])
    register_func = getattr(module, register_func_name)
    register_func()


def ensure_tools_registered() -> None:
    """确保所有工具已注册(全量注册) - 小沈 2026-05-15; 小欧 2026-07-25 加即时重试应对瞬态文件损坏"""
    import time as _time
    global _registered_categories

    _failed = False
    _t_all = _time.time()
    for cat_name, (module_path, register_func) in CATEGORY_MODULES.items():
        if cat_name not in _registered_categories:
            _t_cat = _time.time()
            for _attempt in range(1, 4):
                try:
                    count_before = len(tool_registry._tools)
                    _import_and_register(module_path, register_func)
                    count_after = len(tool_registry._tools)
                    _registered_categories.add(cat_name)
                    if _attempt > 1:
                        logger.info(f"[启动耗时] 工具分类 {cat_name} 注册成功(第{_attempt}次): {_time.time()-_t_cat:.3f}s, {count_after - count_before}个工具")
                    else:
                        logger.info(f"[启动耗时] 工具分类 {cat_name} 注册: {_time.time()-_t_cat:.3f}s, {count_after - count_before}个工具")
                    break
                except Exception as e:
                    _ctx = getattr(e, 'filename', None)
                    if _ctx:
                        _ctx = f"{_ctx}:{getattr(e, 'lineno', '?')} - {e}"
                    else:
                        _ctx = f"{e}"
                    if _attempt < 3:
                        logger.warning(f"[Tools] 注册分类{cat_name}失败(第{_attempt}次),500ms后重试: {_ctx}")
                        _time.sleep(0.5)
                    else:
                        logger.error(f"[Tools] 注册分类{cat_name}失败(已重试3次): {_ctx}")
                        _failed = True
    logger.info(f"[启动耗时] ensure_tools_registered 合计: {_time.time()-_t_all:.3f}s")
    if _failed:
        logger.warning(f"[Tools] 部分分类注册失败,已注册{len(_registered_categories)}个分类,下次调用将重试")
    elif _registered_categories:
        total_tools = len(tool_registry._tools)
        logger.info(f"[Tools] 全部注册完成, {total_tools}个工具, {len(_registered_categories)}个分类")

