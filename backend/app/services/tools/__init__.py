# -*- coding: utf-8 -*-
"""
Tools 模块 - 按意图类型组织的工具集

【2026-05-10 小沈重构】注册机制改造：
- 原设计：模块级import 15个子模块触发注册 → 启动时全量注册118个工具+118条日志
- 新设计：按需注册，首次请求时调用 ensure_tools_registered() 触发
- 原因：tools/__init__.py 被 base_react.py 的 import tools.registry 间接触发，
         导致启动时就全量注册，而非请求时按需注册

调用链路（改造后）：
  启动时: app.main → routes → base_react → import tools.registry → 只加载registry，不触发注册
  请求时: Agent.__init__() → _init_tools_and_executor() → ensure_tools_registered() → 首次触发注册
"""

from app.services.tools.registry import (
    ToolRegistry,
    ToolCategory,
    ToolMetadata,
    tool_registry,
    get_tools_dict,
    get_tools_from_file_registry,
    register_tool,
    get_registered_tools,
    get_tool,
)

from app.services.tools.tool_config import (
    ToolConfig,
    tool_config,
    get_tool_config,
)


# 【Phase 1修复 小健 2026-05-14】分阶段注册：删除模块级自动注册，改为显式调用
_tools_registered = False
_registered_categories: set = set()

# 注册函数映射：分类名 -> (import函数, 注册函数名)
# 注意：注册函数在各*_register.py中定义
_CATEGORY_MODULES = {
    "file": ("app.services.tools.file", "_register_file_tools"),
    "time": ("app.services.tools.time", "_register_time_tools"),
    "shell": ("app.services.tools.shell", "_register_shell_tools"),
    "network": ("app.services.tools.network", "register_network_tools"),
    "environment": ("app.services.tools.environment", "_register_env_tools"),
    "system": ("app.services.tools.system", "_register_system_tools"),
    "database": ("app.services.tools.database", "_register_database_tools"),
    "desktop": ("app.services.tools.desktop", "_register_desktop_tools"),
    "desktop_gui": ("app.services.tools.desktop.gui_register", "_register_gui_tools"),
    "desktop_gui_helpers": ("app.services.tools.desktop.gui_helpers_register", "_register_gui_helpers"),
    "data_format": ("app.services.tools.data_format", "_register_data_format_tools"),
    "code_execution": ("app.services.tools.code_execution", "_register_code_execution_tools"),
    "document": ("app.services.tools.document", "_register_document_tools"),
    "document_data_analysis": ("app.services.tools.document.data_analysis_register", "_register_data_analysis_tools"),
    "support_tool": ("app.services.tools.support_tool", "_register_support_tool_tools"),
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


def ensure_tools_registered(categories: list = None) -> None:
    """确保工具已注册 - 小健 2026-05-14

    全量注册所有分类的工具，忽略categories参数（一次性注册）。
    """
    global _tools_registered, _registered_categories

    if _tools_registered:
        return

    from app.utils.logger import logger
    for cat_name, (module_path, register_func) in _CATEGORY_MODULES.items():
        if cat_name not in _registered_categories:
            _import_and_register(module_path, register_func)
            _registered_categories.add(cat_name)
            logger.info(f"[Tools] 全量注册分类: {cat_name}")
    _tools_registered = True
    logger.info(f"[Tools] 全部工具已注册完成，共{len(_registered_categories)}个分类")


def reset_registered_state() -> None:
    """重置注册状态（仅用于测试） - 小健 2026-05-14
    
    在测试套件中重置注册状态，用于隔离测试。
    """
    global _tools_registered
    _tools_registered = False
    _registered_categories.clear()


def is_tools_registered() -> bool:
    """检查工具是否已注册"""
    return _tools_registered


__all__ = [
    "ToolRegistry",
    "ToolCategory",
    "ToolMetadata",
    "tool_registry",
    "get_tools_dict",
    "get_tools_from_file_registry",
    "register_tool",
    "get_registered_tools",
    "get_tool",
    "ToolConfig",
    "tool_config",
    "get_tool_config",
    "ensure_tools_registered",
    "is_tools_registered",
    "reset_registered_state",
    "_registered_categories",
]
