# -*- coding: utf-8 -*-
"""
安全检查统一管理器

提供安全检查的统一入口，消除safety逻辑分散问题。
将"分析层"安全（CommandParser评分）和"执行层"安全（FileOperationSafety执行）
统一到一个入口。

Author: 小沈 - 2026-05-27
"""

from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from app.utils.logger import logger


class SafetyHook:
    """
    安全检查Hook基类

    新增分类只需实现此接口并注册到SafetyManager。
    遵循OCP原则：对扩展开放，对修改封闭。
    """

    def check(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行安全检查

        Args:
            action: 工具/操作名称
            params: 操作参数

        Returns:
            安全检查结果 {"is_safe": bool, "risk_score": float, "message": str}
        """
        return {"is_safe": True, "risk_score": 0.0, "message": ""}

    async def on_before_execute(self, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        执行前Hook（如备份）

        Returns:
            None表示通过，dict表示拦截结果
        """
        return None

    async def on_after_execute(self, action: str, params: Dict[str, Any], result: Any) -> None:
        """
        执行后Hook（如记录操作历史）
        """
        pass


class SafetyManager:
    """
    安全检查统一管理器

    统一管理所有分类的安全检查Hook，对外暴露单一入口。
    调用方无需了解安全实现的两层结构，符合SLAP原则。

    两层编排：
      ① CommandParser.parse() — 分析层（命令语义解析+风险评估）
      ② Hook.execute_with_safety() — 执行层（备份/回滚/记录）
    """

    def __init__(self):
        self._hooks: Dict[str, SafetyHook] = {}
        self._command_parser = None

    def set_command_parser(self, parser):
        """设置命令解析器（分析层）— 小沈 2026-05-27"""
        self._command_parser = parser
        logger.info("[SafetyManager] 设置CommandParser分析层")

    def parse_command(self, command: str) -> Dict[str, Any]:
        """解析命令语义（分析层）— 小沈 2026-05-27"""
        if self._command_parser is None:
            return {"operation": None, "sources": [], "targets": [], "direction": None, "quantity": "single"}
        return self._command_parser.parse(command)

    def register_hook(self, category: str, hook: SafetyHook):
        """
        注册安全检查Hook

        Args:
            category: 工具分类名（如"file", "network"）
            hook: SafetyHook实例
        """
        self._hooks[category] = hook
        logger.info(f"[SafetyManager] 注册安全Hook: category={category}")

    def check(self, category: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一安全检查入口

        Args:
            category: 工具分类
            action: 操作名称
            params: 操作参数

        Returns:
            安全检查结果
        """
        hook = self._hooks.get(category)
        if hook is None:
            return {"is_safe": True, "risk_score": 0.0, "message": ""}
        return hook.check(action, params)

    async def on_before_execute(self, category: str, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        执行前统一调度

        Args:
            category: 工具分类
            action: 操作名称
            params: 操作参数

        Returns:
            None表示通过，dict表示拦截结果
        """
        hook = self._hooks.get(category)
        if hook is None:
            return None
        return await hook.on_before_execute(action, params)

    async def on_after_execute(self, category: str, action: str, params: Dict[str, Any], result: Any) -> None:
        """
        执行后统一调度
        """
        hook = self._hooks.get(category)
        if hook is None:
            return
        await hook.on_after_execute(action, params, result)

    def get_hook(self, category: str) -> Optional[SafetyHook]:
        """获取指定分类的Hook"""
        return self._hooks.get(category)

    def record_operation(self, category: str, *args, **kwargs) -> str:
        """记录操作统一入口 — 委托给对应分类的hook — 小健 2026-05-28
        
        Args:
            category: 工具分类（如"file"）
            *args, **kwargs: 传递给hook.record_operation()的参数
            
        Returns:
            operation_id: 操作唯一标识符
        """
        hook = self._hooks.get(category)
        if hook is None:
            logger.warning(f"[SafetyManager] 无{category}分类的Hook，返回空operation_id")
            return f"op-nohook-{uuid4().hex[:8]}"
        
        if not hasattr(hook, 'record_operation'):
            logger.warning(f"[SafetyManager] {category}的Hook未实现record_operation，返回空operation_id")
            return f"op-norecord-{uuid4().hex[:8]}"
        
        return hook.record_operation(*args, **kwargs)

    async def check_and_execute(
        self,
        category: str,
        action: str,
        params: Dict[str, Any],
        operation_func: Callable,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """安全检查+执行统一入口 — 先check再execute，SLAP原则

        【小健 2026-05-27】组合check()+on_before_execute()+operation()+on_after_execute()
        调用方只需一个调用，无需了解安全两层结构。

        Args:
            category: 工具分类（如"file", "shell"）
            action: 操作名称
            params: 操作参数
            operation_func: 实际执行函数
            *args, **kwargs: 传递给operation_func的参数

        Returns:
            {"is_safe": bool, "check_result": dict, "execution_result": Any, "error": str|None}
        """
        check_result = self.check(category, action, params)
        if not check_result.get("is_safe", True):
            return {
                "is_safe": False,
                "check_result": check_result,
                "execution_result": None,
                "error": check_result.get("message", "安全检查未通过"),
            }

        before_result = await self.on_before_execute(category, action, params)
        if before_result is not None:
            return {
                "is_safe": False,
                "check_result": check_result,
                "execution_result": before_result,
                "error": "执行前安全Hook拦截",
            }

        try:
            result = operation_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"[SafetyManager] 执行失败: {e}")
            return {
                "is_safe": True,
                "check_result": check_result,
                "execution_result": None,
                "error": str(e),
            }

        await self.on_after_execute(category, action, params, result)
        return {
            "is_safe": True,
            "check_result": check_result,
            "execution_result": result,
            "error": None,
        }

    def execute_with_safety(self, category: str, operation_id: str, operation_func: Callable, *args, **kwargs) -> bool:
        """安全执行统一入口 — DRY原则：所有分类的安全执行走此入口
        
        【重构 2026-05-27 小健】遵循DRY+OCP原则：
        - 统一入口，消除file_safety独立实现
        - 委托给对应分类的hook.execute_with_safety()
        - 新增分类只需注册hook即可获得安全执行能力
        
        Args:
            category: 工具分类（如"file"）
            operation_id: 操作ID
            operation_func: 实际执行函数
            *args, **kwargs: 传递给operation_func的参数
            
        Returns:
            执行是否成功
        """
        hook = self._hooks.get(category)
        if hook is None:
            logger.warning(f"[SafetyManager] 无{category}分类的Hook，直接执行")
            try:
                return operation_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"[SafetyManager] 直接执行失败: {e}")
                return False
        
        if not hasattr(hook, 'execute_with_safety'):
            logger.warning(f"[SafetyManager] {category}的Hook未实现execute_with_safety，直接执行")
            try:
                return operation_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"[SafetyManager] 直接执行失败: {e}")
                return False
        
        return hook.execute_with_safety(operation_id, operation_func, *args, **kwargs)


# 全局单例
_safety_manager: Optional[SafetyManager] = None


def get_safety_manager() -> SafetyManager:
    """获取SafetyManager单例 — 自动加载CommandParser — 小沈 2026-05-27"""
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManager()
        try:
            from app.services.command_parser.parser import CommandParser
            _safety_manager.set_command_parser(CommandParser())
        except Exception as e:
            logger.warning(f"[SafetyManager] CommandParser加载失败: {e}")
    return _safety_manager


__all__ = ["SafetyHook", "SafetyManager", "get_safety_manager"]
