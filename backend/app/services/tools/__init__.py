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


# 【Phase 1 小健 2026-05-14】分阶段注册：支持按分类注册，而非一次性全注册
_tools_registered = False
_registered_categories: set = set()

_CATEGORY_MODULES = {
    "file": lambda: __import__("app.services.tools.file", fromlist=["file"]),
    "time": lambda: __import__("app.services.tools.time", fromlist=["time"]),
    "shell": lambda: __import__("app.services.tools.shell", fromlist=["shell"]),
    "network": lambda: __import__("app.services.tools.network", fromlist=["network"]),
    "environment": lambda: __import__("app.services.tools.environment", fromlist=["environment"]),
    "system": lambda: __import__("app.services.tools.system", fromlist=["system"]),
    "database": lambda: __import__("app.services.tools.database", fromlist=["database"]),
    "desktop": lambda: __import__("app.services.tools.desktop", fromlist=["desktop"]),
    "data_format": lambda: __import__("app.services.tools.data_format", fromlist=["data_format"]),
    "code_execution": lambda: __import__("app.services.tools.code_execution", fromlist=["code_execution"]),
    "document": lambda: __import__("app.services.tools.document", fromlist=["document"]),
    "support_tool": lambda: __import__("app.services.tools.support_tool", fromlist=["support_tool"]),
}


def ensure_tools_registered(categories: list = None) -> None:
    """确保工具已注册 - 小健 2026-05-14

    【Phase 1改造】支持按分类注册：
    - categories=None: 注册全部（兼容旧行为）
    - categories=["network"]: 只注册network分类

    调用位置：
    - ReactAgentMixin._init_tools_and_executor() — 按当前分类注册
    - base_react.load_tools_by_intent() — 动态加载新分类
    """
    global _tools_registered, _registered_categories

    if categories is None:
        # 全量注册（兼容旧行为）
        if _tools_registered:
            return
        for cat_name, import_fn in _CATEGORY_MODULES.items():
            if cat_name not in _registered_categories:
                import_fn()
                _registered_categories.add(cat_name)
        _tools_registered = True
        from app.utils.logger import logger
        logger.info(f"[Tools] 全部工具已注册完成，共{len(_registered_categories)}个分类")
    else:
        # 按分类注册
        from app.utils.logger import logger
        for cat_name in categories:
            if cat_name in _registered_categories:
                continue
            if cat_name in _CATEGORY_MODULES:
                _CATEGORY_MODULES[cat_name]()
                _registered_categories.add(cat_name)
                logger.info(f"[Tools] 按需注册分类: {cat_name}")
        if len(_registered_categories) >= len(_CATEGORY_MODULES):
            _tools_registered = True


def reset_registered_state() -> None:
    """重置注册状态（仅用于测试） - 小健 2026-05-14
    
    在测试套件中，如果需要测试"按分类注册"的正确性，
    应在每个测试用例开始时调用此函数重置状态。
    
    注意：此函数只重置_registered_categories和_tools_registered标志，
    不会清空tool_registry._tools中已注册的工具。
    
    示例：
        from app.services.tools import reset_registered_state, ensure_tools_registered, _registered_categories
        
        def test_category_registration():
            reset_registered_state()
            ensure_tools_registered(categories=["network"])
            assert "network" in _registered_categories
            assert "file" not in _registered_categories
    """
    global _tools_registered
    _tools_registered = False
    _registered_categories.clear()  # 用clear而不是赋值新set，保持引用


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
