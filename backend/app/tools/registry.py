
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-25 - 小欧 - ensure_tools_registered加即时重试(3次,500ms间隔),应对并发写导致的瞬态文件损坏
# 2026-07-25 - 小欧 - 错误日志加filename:lineno上下文(欧阳建议)
# 2026-08-07 - 小欧 - get_tool工具名别名归一化: LLM常生成变体名(write_text等), 经tools_alias_mapper.normalize_tool_name映射到注册名(write), 防"工具未注册"误拦截(com-test 03暴露)
# 2026-08-18 - 小健 - ToolMetadata 新增 target_param 字段(操作对象/主参数显式声明扩展点), register/register_tool 贯通透传; 供 action_handler._resolve_target_field 优先采用, 留空则按schema属性自动推导(DRY/OCP)
# 2026-10-15 - 小欧 - 跟随改名: TOOL_ACTION_KINDS→PATH_ACTION_KINDS(旧名不留壳); _resolve_action_kind 收口注册/重注册两处缺省(DRY)。
# 2026-10-17 - 小欧 - 新增 resolve_registered_tool: 未注册判定唯一真源(解析层第一步调用, 替代三处复判)。
# 2026-10-18 - 小欧 - 新增 confirm_fn/op_param 两字段, register/_update/_register/装饰器 四处贯通(各2行)。
# 2026-10-19 - 小欧 - 依赖治理接线: _check_dependencies 返回值 bool→缺失清单(原先算完即弃, 结论无处落地),
#   register 写入 ToolMetadata.available/missing_deps; 新增 _declared_deps(扫各 *_register 的依赖声明)
#   + preinstall_tool_dependencies(启动期一次 pip 装齐); 运行期自愈拆 heal_missing_deps(工作线程只装)
#   与 apply_heal_result(主线程写元数据), 免跨线程改共享元数据读到中间态。
# 2026-10-19 - 小欧 - list_tools 的 expose_to_llm_only 改读 visible_to_llm, 与 tool_description 同判据。
"""
工具注册表模块 - 统一入口

【架构规范】2026-04-26 小沈

拆分自 884行 → ~250行 — 小沈 2026-05-29
移出内容: ToolCategory/ToolMetadata → tool_types.py, Schema处理 → schema_utils.py,
         查询函数 → tool_queries.py, 格式转换 → tool_description.py
"""

from typing import Dict, List, Optional, Callable, Any, Type, Set, Union, Tuple
from pydantic import BaseModel
from app.tools.tool_types import ToolCategory, ToolMetadata
from app.tools.schema_utils import _generate_input_schema
from app.tools.tool_description import to_openai_tools, generate_param_reminder
from app.tools.tools_alias_mapper import normalize_tool_name
from app.logger import setup_logger
from app.utils.dependency import ensure_dependency, install_missing, normalize_dep, dep_install_spec
from app.tools.tool_constants import (  # 2026-10-16 小欧 - 四表分立: 原 PATH_ACTION_KINDS 混放四档
    CATEGORY_MODULES, READ_PATH_TOOLS, WRITE_PATH_TOOLS,
    DELETE_PATH_TOOLS, DUAL_PATH_TOOLS,
)


def _resolve_action_kind(name: str, fallback: str) -> str:
    """工具动作类型: 四档声明表依次命中, 全未声明取 fallback — 小欧 2026-10-15 / 2026-10-16 四表分立
    2026-10-15 小欧 - 原在注册/重注册两处各写一遍查表, 缺省不同, 易改一处漏一处(DRY)。现收于本函数, 两处共用。
    2026-10-16 小欧 - 四表分立: 原单张 PATH_ACTION_KINDS 混放四档, 现读/写/删/双路径各自独立成表,
      本函数按档依次查(直线 if, 不建派发表), 未声明即 fallback。
    """
    if name in READ_PATH_TOOLS:
        return "read"
    if name in WRITE_PATH_TOOLS:
        return "write"
    if name in DELETE_PATH_TOOLS:
        return "delete"
    if name in DUAL_PATH_TOOLS:
        return "dual"
    return fallback

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
    
    def _check_dependencies(self, dependencies: List[Union[str, Dict[str, Any]]], tool_name: str) -> List[str]:
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
            List[str]: 不可用的依赖规格串(空列表=全部可用)。
            2026-10-19 小欧 - 原返回 bool 且调用方直接丢弃, 结论无处落地;
              改为回缺失清单, 由 register 写入 metadata.available / missing_deps。
        """
        if not dependencies:
            return []

        missing: List[str] = []
        for dep in dependencies:
            # 2026-10-19 小欧 - 三处扁平化收口到 normalize_dep: 原先批量预检与自愈各写一遍,
            #   且把 dict 声明压成 pip 名再 import, python-docx/python-pptx/pywin32 恒判缺库。
            imp, pkg, version, pre_install = normalize_dep(dep)
            if imp is None:
                logger.error(f"[ToolRegistry] 工具 '{tool_name}' 依赖配置错误: {dep}")
                missing.append(str(dep))
                continue

            spec = dep_install_spec(imp, pkg, version)
            if not ensure_dependency(imp, pkg, version, pre_install):
                logger.warning(f"[ToolRegistry] 工具 '{tool_name}' 依赖 '{spec}' 安装失败，工具不可用")
                missing.append(spec)

        return missing
    
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
        confirm_fn: Optional[Callable] = None,
        op_param: Optional[str] = None,
        dependencies: Optional[List[Union[str, Dict[str, Any]]]] = None,
        target_param: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        注册工具（单一入口，委托给私有方法）
        
        【修复 2026-06-08 小沈】拆分为私有方法，遵守SRP原则
        【2026-06-16 小沈】用二元安全参数替代5级枚举
        【2026-06-18 小健】添加依赖管理参数
        """
        input_schema = _generate_input_schema(input_model, input_schema)

        # 2026-10-19 小欧 - 检查结论落地: 原 self._check_dependencies(...) 返回值直接丢弃,
        #   缺库工具照样进注册表并出现在 LLM 工具列表, LLM 试调才知不可用、白耗一轮。
        #   现把缺失清单写进元数据, 由 to_openai_tools 过滤、直调时回统一缺库契约。
        deps = dependencies or []
        missing = self._check_dependencies(deps, name)

        # 职责1：更新已存在工具
        if name in self._tools:
            return self._update_existing_tool(
                name, description, category, implementation,
                input_schema, examples, version, deps,
                expose_to_llm, failure_hint_fn,
                needs_confirmation, action_confirmation, confirm_fn, op_param,
                target_param, missing,
            )

        # 职责2：注册新工具
        return self._register_new_tool(
            name, description, category, implementation,
            input_schema, examples, version,
            expose_to_llm, failure_hint_fn,
            needs_confirmation, action_confirmation, confirm_fn, op_param, deps,
            target_param, missing,
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
        confirm_fn: Optional[Callable] = None,
        op_param: Optional[str] = None,
        target_param: Optional[str] = None,
        missing_deps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """更新已注册工具 — chendyg 2026-06-26 修复: 补全所有字段更新和分类索引"""
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
            confirm_fn=confirm_fn,
            op_param=op_param,
            target_param=target_param,
            # 2026-10-15 小欧 - 原缺省直取 .action_kind, 旧实例无该字段会 AttributeError。
            action_kind=_resolve_action_kind(name, getattr(self._tools[name], "action_kind", "write")),
            # 2026-10-19 小欧 - 重注册须一并刷新依赖结论, 否则换依赖后仍沿用旧的 missing_deps。
            available=not missing_deps,
            missing_deps=list(missing_deps or []),
        )
        self._implementations[name] = implementation
        # 【修复】更新分类索引(类别可能变更) — chendyg 2026-06-26
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
        confirm_fn: Optional[Callable] = None,
        op_param: Optional[str] = None,
        dependencies: List[Union[str, Dict[str, Any]]] = None,
        target_param: Optional[str] = None,
        missing_deps: Optional[List[str]] = None,
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
            confirm_fn=confirm_fn,
            op_param=op_param,
            dependencies=dependencies or [],
            target_param=target_param,
            # 2026-10-15 小欧 - 动作类型按声明表赋值, 未列者取 fallback(fail-closed 最严档)
            action_kind=_resolve_action_kind(name, "write"),
            # 2026-10-19 小欧 - 依赖检查结论落元数据: 缺库仍注册但对 LLM 不可见。
            available=not missing_deps,
            missing_deps=list(missing_deps or []),
        )
        self._tools[name] = metadata
        self._implementations[name] = implementation
        self._update_category_index(category, name)
        logger.debug(f"Tool registered: {name} (category: {category.value}, needs_confirmation: {needs_confirmation}, dependencies: {dependencies}, missing_deps: {missing_deps or []})")
        return {"status": "success"}
    
    def _update_category_index(self, category: ToolCategory, name: str) -> None:
        """更新分类索引"""
        self._categories.setdefault(category, [])
        if name not in self._categories[category]:
            self._categories[category].append(name)
    

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据(返回dataclass)
        2026-08-07 小欧: 工具名别名归一化——LLM常生成变体名(write_text等),
        精确匹配失败时经 tools_alias_mapper.normalize_tool_name 映射到注册名(write),
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

    def heal_missing_deps(self, name: str) -> List[str]:
        """缺库兜底重装(A方案: 运行期惰性), 返回仍缺的依赖规格串 — 小欧 2026-10-19

        覆盖启动期批量装失败的情形(离线、镜像不可达、打包版)。
        只认工具自己声明过的依赖, 不凭空装任何东西; 锁定包走 dependency 护栏。

        2026-10-19 小欧 - 刻意**不改元数据**: 本函数经 to_thread 在工作线程执行,
          而事件循环可能同时在 to_openai_tools 读 meta.visible_to_llm。跨线程写共享
          对象会读到"available 已翻、missing_deps 还没写"的中间态, 错误文案便少列依赖。
          故本函数只负责装与返回, 写元数据交 apply_heal_result 在主线程做。
        """
        meta = self._tools.get(name)
        if meta is None or meta.available:
            return []
        # 声明经 normalize_dep 归一, import 名与 pip 名不混用(dict 声明的 python-docx 之类才判得对)
        deps = [d for d in (normalize_dep(x) for x in (meta.dependencies or [])) if d[0]]
        return [dep_install_spec(*d[:3]) for d in install_missing(deps)]

    def apply_heal_result(self, name: str, missing: List[str]) -> bool:
        """把自愈结果写进元数据(须在主线程调用), 返回是否已恢复可用 — 小欧 2026-10-19

        与 heal_missing_deps 拆开是因为跨线程写共享元数据会读到中间态, 见该函数说明。
        """
        meta = self._tools.get(name)
        if meta is None:
            return True
        meta.missing_deps = list(missing)
        meta.available = not missing
        if missing:
            logger.warning(f"[依赖自愈] 工具 '{name}' 仍缺 {', '.join(meta.missing_deps)}")
        else:
            logger.info(f"[依赖自愈] 工具 '{name}' 依赖已补齐, 恢复可用")
        return meta.available

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
            # 2026-10-19 小欧 - 改读 visible_to_llm(依赖齐备才算暴露面): 此处仍是旧字段,
            #   与 tool_description 的单一判据口径不一致, 漏改会分裂"该不该给 LLM"的定义。
            tool_names = [name for name in tool_names if self._tools[name].visible_to_llm]

        
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


def resolve_registered_tool(tool_name: str) -> Tuple[Optional[str], Optional[ToolMetadata]]:
    """归一化工具名 + 查注册表, 未注册判定唯一真源 — 小欧 2026-10-17
    返回 (normal_name, meta); meta is None 即未注册, 由解析层第一步拦截(下游不复判)。
    """
    normal_name = normalize_tool_name(tool_name)
    return normal_name, tool_registry.get_tool(normal_name)


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
    confirm_fn: Optional[Callable] = None,
    op_param: Optional[str] = None,
    dependencies: Optional[List[Union[str, Dict[str, Any]]]] = None,
    target_param: Optional[str] = None,
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
            confirm_fn=confirm_fn,
            op_param=op_param,
            dependencies=dependencies,
            target_param=target_param,
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


def _declared_deps() -> List[tuple]:
    """扫描各 <cat>_register 的 *TOOL_DEPENDENCIES, 归一成 (imp, pkg, ver, pre) 列表

    — 小欧 2026-10-19
    依赖声明散在 9 个 *_register.py 的 TOOL_DEPENDENCIES / NETWORK_TOOL_DEPENDENCIES 等表里,
    名字不统一, 故按后缀匹配而非硬编码表名(新增分类无需改此处)。
    每条经 dependency.normalize_dep 归一, 免得 import 名与 pip 名在此处被混用。
    """
    out: List[tuple] = []
    seen = set()
    for cat_name, (module_path, _register_func) in CATEGORY_MODULES.items():
        # 依赖表在 <cat>_register 模块里, 而 CATEGORY_MODULES 指向的是包本身(app.tools.<cat>)
        reg_path = f"{module_path}.{cat_name}_register"
        try:
            module = __import__(reg_path, fromlist=["_collect"])
        except Exception as e:
            logger.warning(f"[依赖预装] 扫描 {cat_name} 依赖声明失败: {e}")
            continue
        for attr, value in vars(module).items():
            if not attr.endswith("TOOL_DEPENDENCIES") or not isinstance(value, dict):
                continue
            for deps in value.values():
                for dep in deps or []:
                    norm = normalize_dep(dep)
                    if norm[0] is None:
                        continue
                    if norm not in seen:
                        seen.add(norm)
                        out.append(norm)
    return out


def preinstall_tool_dependencies() -> List[str]:
    """启动期批量装依赖(纯检查→一次 pip 装全部→复检), 返回仍未就位的规格串 — 小欧 2026-10-19

    原本每个依赖各起一次 pip 子进程(N 个依赖 N 次, 每次都付一次解释器冷启动)。
    装包统一走 dependency.install_missing(唯一装包入口), 免得判缺失那一步自己把包单装掉,
    导致批量化空转。锁定包由 dependency.LOCKED_PACKAGES 经 pip 约束文件保护。
    """
    import time as _time
    from app.utils.dependency import install_missing

    _t = _time.time()
    deps = _declared_deps()
    if not deps:
        return []
    still = install_missing(deps)
    logger.info(f"[启动耗时] preinstall_tool_dependencies({len(deps)} 依赖): {_time.time() - _t:.3f}s")
    return [dep_install_spec(*d[:3]) for d in still]


def ensure_tools_registered() -> None:
    """确保所有工具已注册(全量注册) - 小沈 2026-05-15; 小欧 2026-07-25 加即时重试应对瞬态文件损坏"""
    import time as _time
    global _registered_categories

    _failed = False
    _t_all = _time.time()
    preinstall_tool_dependencies()   # 小欧 2026-10-19: 先批量装齐, 下面注册期就只剩 import 探测
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

