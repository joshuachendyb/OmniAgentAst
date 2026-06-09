# -*- coding: utf-8 -*-
"""
安全检查统一管理器 — 简化版

小健 - 2026-06-07 删除CommandParser分析层,只保留执行层Hook

Author: 小沈 - 2026-05-27
"""

from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from app.utils.logger import logger


class SafetyHook:
    """
    安全检查Hook基类
    """

    def check(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"is_safe": True, "risk_score": 0.0, "message": ""}

    async def on_before_execute(self, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_after_execute(self, action: str, params: Dict[str, Any], result: Any) -> None:
        pass


class SafetyManager:
    """
    安全检查统一管理器 — 简化版(只保留执行层)
    """

    def __init__(self):
        self._hooks: Dict[str, SafetyHook] = {}

    def register_hook(self, category: str, hook: SafetyHook):
        self._hooks[category] = hook
        logger.info(f"[SafetyManager] 注册安全Hook: category={category}")

    def check(self, category: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        hook = self._hooks.get(category)
        if hook is None:
            return {"is_safe": True, "risk_score": 0.0, "message": ""}
        return hook.check(action, params)

    async def on_before_execute(self, category: str, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        hook = self._hooks.get(category)
        if hook is None:
            return None
        return await hook.on_before_execute(action, params)

    async def on_after_execute(self, category: str, action: str, params: Dict[str, Any], result: Any) -> None:
        hook = self._hooks.get(category)
        if hook is None:
            return
        await hook.on_after_execute(action, params, result)

    def get_hook(self, category: str) -> Optional[SafetyHook]:
        return self._hooks.get(category)

    def record_operation(self, category: str, *args, **kwargs) -> str:
        hook = self._hooks.get(category)
        if hook is None or not hasattr(hook, 'record_operation'):
            return f"op-nohook-{uuid4().hex[:8]}"
        return hook.record_operation(*args, **kwargs)

    def execute_with_safety(self, category: str, operation_id: str, operation_func: Callable, *args, **kwargs) -> bool:
        hook = self._hooks.get(category)
        if hook is None or not hasattr(hook, 'execute_with_safety'):
            try:
                return operation_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"[SafetyManager] 直接执行失败: {e}")
                return False
        return hook.execute_with_safety(operation_id, operation_func, *args, **kwargs)


# 全局单例
_safety_manager: Optional[SafetyManager] = None


def get_safety_manager() -> SafetyManager:
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManager()
    return _safety_manager


__all__ = ["SafetyHook", "SafetyManager", "get_safety_manager"]
