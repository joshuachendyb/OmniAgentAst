"""
Tools 注册管理模块

【2026-05-10 小沈重构】注册机制改造：
- 原设计：模块级import 15个子模块触发注册 → 启动时全量注册118个工具+118条日志
- 新设计：按需注册，首次请求时调用 ensure_tools_registered() 触发
- 原因：tools/__init__.py 被 base_react.py 的 import tools.registry 间接触发，
         导致启动时就全量注册，而非请求时按需注册

调用链路（改造后）：
  启动时: app.main → routes → base_react → import tools.registry → 只加载registry，不触发注册
  请求时: Agent.__init__() → _init_tools_and_executor() → ensure_tools_registered() → 首次触发注册
"""


# 【Phase 1修复 小健 2026-05-14】分阶段注册：删除模块级自动注册，改为显式调用
_tools_registered = False
_registered_categories: set = set()

# 【Phase 3 小沈 2026-05-18】精简方案：14→7注册模块
_CATEGORY_MODULES = {
    "file": ("app.services.tools.file", "_register_file_tools"),
    "shell": ("app.services.tools.shell", "_register_shell_tools"),
    "network": ("app.services.tools.network", "_register_network_tools"),
    "system": ("app.services.tools.system", "_register_system_tools"),
    "desktop": ("app.services.tools.desktop", "_register_desktop_tools"),
    "document": ("app.services.tools.document", "_register_document_tools"),
    "meta": ("app.services.tools.meta", "_register_meta_tools"),
}


def _import_and_register(module_path: str, register_func_name: str) -> None:
    """导入模块并调用注册函数 - 小健 2026-05-14"""
    module = __import__(module_path, fromlist=[register_func_name])
    register_func = getattr(module, register_func_name, None)
    if register_func:
        register_func()
    else:
        # 如果__init__.py没导出register函数，尝试从register模块获取
        register_module_name = module_path.rsplit(".", 1)[1] + "_register"
        register_module_path = f"{module_path}.{register_module_name}"
        try:
            register_module = __import__(register_module_path, fromlist=[register_func_name])
            register_func = getattr(register_module, register_func_name)
            register_func()
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"[Tools] 无法找到注册函数 {register_func_name}: {e}")


def ensure_tools_registered() -> None:
    """确保所有工具已注册（全量注册） - 小沈 2026-05-15
    
    【修复 U8】移除categories参数，明确声明为全量注册。
    """
    global _tools_registered, _registered_categories

    if _tools_registered:
        return

    from app.utils.logger import logger
    _failed = False
    for cat_name, (module_path, register_func) in _CATEGORY_MODULES.items():
        if cat_name not in _registered_categories:
            try:
                _import_and_register(module_path, register_func)
                _registered_categories.add(cat_name)
                logger.info(f"[Tools] 全量注册分类: {cat_name}")
            except Exception as e:
                logger.error(f"[Tools] 注册分类{cat_name}失败: {e}")
                _failed = True
    # 【修复 问题5 小沈 2026-05-15】有分类注册失败时不标记完成
    if not _failed:
        _tools_registered = True
        logger.info(f"[Tools] 全部工具已注册完成，共{len(_registered_categories)}个分类")
    else:
        logger.warning(f"[Tools] 部分分类注册失败，已注册{len(_registered_categories)}个分类，下次调用将重试")


def reset_registered_state() -> None:
    """重置注册状态（仅用于测试） - 小健 2026-05-14
    
    在测试套件中重置注册状态，用于隔离测试。
    """
    from app.services.tools.registry import tool_registry
    global _tools_registered
    _tools_registered = False
    _registered_categories.clear()
    tool_registry._tools.clear()
    tool_registry._categories.clear()
    tool_registry._implementations.clear()


def is_tools_registered() -> bool:
    """检查工具是否已注册"""
    return _tools_registered


__all__ = [
    "ensure_tools_registered",
    "is_tools_registered",
    "reset_registered_state",
]
