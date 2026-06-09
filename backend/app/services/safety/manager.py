# -*- coding: utf-8 -*-
"""
安全检查统一管理器 — 四层纵深安全体系

小健 - 2026-06-07 删除CommandParser分析层,只保留执行层Hook
小沈 - 2026-06-09 v3.4新增Layer 2工具安全级别检查

Author: 小沈 - 2026-05-27
"""

from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from app.utils.logger import logger
from app.services.tools.tool_types import ToolSafetyLevel, DEFAULT_SAFETY_POLICY


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
        """
        执行层安全检查（Hook模式）
        
        【v3.4修复漏洞#2】Hook缺失时改为默认拒绝 — 小沈 2026-06-09
        """
        hook = self._hooks.get(category)
        if hook is None:
            return {"is_safe": False, "risk_score": 1.0, "message": f"未注册安全Hook: {category}"}
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

    def check_tool_safety(self, tool_name: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Layer 2工具安全级别检查 — 统一安全检查入口
        
        从ToolMetadata读取safety_level，并调用已有安全能力
        
        【v3.4新增】小沈 2026-06-09
        """
        from app.services.tools.registry import tool_registry
        
        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            return {"is_safe": False, "risk_score": 1.0, "message": f"工具{tool_name}未注册", "blocked": True}

        # 1. 解析安全等级
        safety_level = self._resolve_safety_level(tool_meta, params or {})
        policy = DEFAULT_SAFETY_POLICY.get(safety_level, DEFAULT_SAFETY_POLICY[ToolSafetyLevel.SAFE])

        # 2. 调用已有安全能力（复用优先）
        existing_check_result = self._check_existing_safety_capabilities(tool_name, params or {})
        if existing_check_result and not existing_check_result.get("is_safe", True):
            return existing_check_result  # 已有安全能力拦截，直接返回

        # 3. 返回安全检查结果
        risk_score_map = {
            ToolSafetyLevel.READ_ONLY: 0.0,
            ToolSafetyLevel.SAFE: 0.3,
            ToolSafetyLevel.DESTRUCTIVE: 0.7,
            ToolSafetyLevel.DANGEROUS_SANDBOX: 0.85,
            ToolSafetyLevel.DANGEROUS: 1.0,
        }
        
        return {
            "is_safe": not policy["needs_confirmation"],
            "risk_score": risk_score_map[safety_level],
            "safety_level": safety_level.value,
            "requires_confirmation": policy["needs_confirmation"],
            "blocked": False,
            "message": "",
        }

    @staticmethod
    def _resolve_safety_level(tool_meta, params: Dict) -> ToolSafetyLevel:
        """
        解析安全等级：优先查action_safety_map，否则用工具级safety_level
        
        【v3.4新增】小沈 2026-06-09
        """
        if tool_meta.action_safety_map and params.get("action"):
            return tool_meta.action_safety_map.get(params["action"], tool_meta.safety_level)
        return tool_meta.safety_level

    @staticmethod
    def _check_existing_safety_capabilities(tool_name: str, params: Dict) -> Optional[Dict]:
        """
        调用已有安全能力（复用优先原则）
        
        【v3.4新增】小沈 2026-06-09
        【v3.5优化】使用tool_registry.get_categories()动态获取工具列表 — 小沈 2026-06-09
        """
        from app.services.tools.registry import tool_registry
        from app.services.tools.tool_types import ToolCategory
        
        # 动态获取FILE分类下的工具
        all_categories = tool_registry.get_categories()
        file_tools = set(all_categories.get(ToolCategory.FILE, []))
        
        # 文件工具：路径白名单检查
        if tool_name in file_tools:
            try:
                from app.services.tools.file.file_tools import FileTools
                path = params.get("path") or params.get("source_path") or params.get("target_path")
                if path:
                    is_valid, msg = FileTools._validate_path(path)
                    if not is_valid:
                        return {"is_safe": False, "risk_score": 1.0, "blocked": True, "message": f"路径检查失败: {msg}"}
            except Exception as e:
                logger.warning(f"[SafetyManager] 路径检查失败: {e}")
        
        # 写入工具：内容质量检查
        if tool_name == "write_text_file":
            try:
                from app.services.tools.file.file_tools import FileTools
                content = params.get("content", "")
                path = params.get("path", "")
                is_safe, msg = FileTools._check_write_safety(content, path)
                if not is_safe:
                    return {"is_safe": False, "risk_score": 0.8, "blocked": True, "message": f"写入检查失败: {msg}"}
            except Exception as e:
                logger.warning(f"[SafetyManager] 写入检查失败: {e}")
        
        # Shell/Python/JS执行：代码注入检查
        # 动态获取FUND_RUNTIME分类下的代码执行工具
        fund_runtime_tools = set(all_categories.get(ToolCategory.FUND_RUNTIME, []))
        code_exec_tools = {"execute_shell_command", "execute_python", "execute_js"} & fund_runtime_tools
        if tool_name in code_exec_tools:
            try:
                from app.services.tools.tool_constants import DANGEROUS_PATTERNS
                code = params.get("command") or params.get("code") or ""
                for pattern in DANGEROUS_PATTERNS:
                    if pattern.search(code):
                        return {"is_safe": False, "risk_score": 1.0, "blocked": True,
                                "message": f"检测到危险模式: {pattern.pattern}"}
            except Exception as e:
                logger.warning(f"[SafetyManager] 代码注入检查失败: {e}")
        
        return None  # 无拦截，继续后续检查

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


__all__ = ["SafetyHook", "SafetyManager", "get_safety_manager", "ToolSafetyLevel", "DEFAULT_SAFETY_POLICY"]
