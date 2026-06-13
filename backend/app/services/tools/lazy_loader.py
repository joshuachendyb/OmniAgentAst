"""
Tools 懒加载模块(原 registration.py)

【2026-05-10 小沈重构】注册机制改造:
 - 原设计:模块级import 15个子模块触发注册 → 启动时全量注册118个工具+118条日志
 - 新设计:按需注册,首次请求时调用 ensure_tools_registered() 触发
 - 原因:tools/__init__.py 被 import tools.registry 间接触发,
          导致启动时就全量注册,而非请求时按需注册

【2026-05-29 小健】重命名:registration.py → lazy_loader.py
- 原因:registration 与 registry 命名混淆,lazy_loader 更清晰表达"懒加载"职责

调用链路(改造后):
   启动时: app.main → routes → import tools.registry → 只加载registry,不触发注册
  请求时: Agent.__init__() → _init_tools_and_executor() → ensure_tools_registered() → 首次触发注册
"""


_registered_categories: set = set()

# 常量已迁移到 tool_constants.py — 北京老陈 2026-05-30
from app.services.tools.tool_constants import CATEGORY_MODULES


def _import_and_register(module_path: str, register_func_name: str) -> None:
    """导入模块并调用注册函数 - 小健 2026-05-14"""
    module = __import__(module_path, fromlist=[register_func_name])
    register_func = getattr(module, register_func_name, None)
    if register_func:
        register_func()
    else:
        # 如果__init__.py没导出register函数,尝试从register模块获取
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
    """确保所有工具已注册(全量注册) - 小沈 2026-05-15
    
    无冷启动门闩:每次调用都检查未注册分类,新分类可随时加入CATEGORY_MODULES
    """
    global _registered_categories

    from app.utils.logger import logger
    from app.services.tools.registry import tool_registry
    _failed = False
    for cat_name, (module_path, register_func) in CATEGORY_MODULES.items():
        if cat_name not in _registered_categories:
            try:
                count_before = len(tool_registry._tools)
                _import_and_register(module_path, register_func)
                count_after = len(tool_registry._tools)
                _registered_categories.add(cat_name)
                logger.info(f"[Tools] 分类 {cat_name} 注册完成, {count_after - count_before}个工具")
            except Exception as e:
                logger.error(f"[Tools] 注册分类{cat_name}失败: {e}")
                _failed = True
    if _failed:
        logger.warning(f"[Tools] 部分分类注册失败,已注册{len(_registered_categories)}个分类,下次调用将重试")
    elif _registered_categories:
        total_tools = len(tool_registry._tools)
        logger.info(f"[Tools] 全部注册完成, {total_tools}个工具, {len(_registered_categories)}个分类")


__all__ = [
    "ensure_tools_registered",
]
