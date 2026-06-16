# -*- coding: utf-8 -*-
"""
工具安全检查器 — 执行前安全检查

Layer 2: 二元安全确认(needs_confirmation)
Layer 3: 已知风险检测(路径越权/写入污染/代码注入)

2026-06-16 小沈 删除5级枚举，改用二元安全+check_fn
"""

import os
from typing import Any, Dict, Optional

from app.utils.logger import logger

_WRITE_RISK_TOOL = "write_text_file"
_CODE_INJECTION_RISK_TOOLS = {"execute_shell_command", "execute_code"}

# 安全开关 — 唯一入口: config.yaml security.enabled
# 关闭: config.yaml 设 security.enabled: false
# 启用: config.yaml 设 security.enabled: true (默认)
def _is_skip_safety() -> bool:
    """运行时检查安全开关 — 只读 config.yaml security.enabled"""
    try:
        from app.config import get_config
        return not get_config().get("security.enabled", True)
    except Exception:
        return False


class ToolSafetyChecker:
    """工具执行前安全检查 — 确认判定 + 已知风险检测"""

    def record_operation(self, category: str, **kwargs) -> str:
        """记录操作 — 委托 file_safety.record_operation 做DB事务"""
        from app.services.safety.file.file_safety import record_operation as _real_record
        return _real_record(**kwargs)

    def execute_with_safety(self, category: str, **kwargs) -> bool:
        """安全执行 — 委托 file_safety.execute_with_safety 做编排"""
        from app.services.safety.file.file_safety import execute_with_safety as _real_exec
        return _real_exec(**kwargs)


    def check_before_execute(self, tool_name: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行前安全检查入口

        安全开关: config.yaml security.enabled=false 时跳过所有检查

        Returns:
            {"is_safe", "requires_confirmation", "blocked", "message", "safety_level"}
        """
        if _is_skip_safety():
            return {"is_safe": True, "requires_confirmation": False,
                    "blocked": False, "message": "安全开关已绕过",
                    "safety_level": "safe"}

        from app.services.tools.registry import tool_registry

        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            return {"is_safe": False, "blocked": True,
                    "message": f"工具{tool_name}未注册",
                    "safety_level": "dangerous"}

        # 已知风险检测（独立于needs_confirmation）
        known_risk = self._check_known_risks(tool_name, params or {})
        if known_risk and not known_risk.get("is_safe", True):
            known_risk["safety_level"] = "dangerous"
            return known_risk

        # 确认判定：action级 > 工具级
        needs_confirm = self._get_needs_confirmation(tool_meta, params or {})

        # 自定义检查（check_fn优先）
        if tool_meta.check_fn:
            try:
                custom_result = tool_meta.check_fn(params or {})
                if not custom_result.get("is_safe", True):
                    custom_result["safety_level"] = custom_result.get("safety_level", "dangerous")
                    return custom_result
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] check_fn异常,阻止执行: {e}")
                return {"is_safe": False, "blocked": True,
                        "message": f"安全检查异常(已阻止): {e}",
                        "safety_level": "dangerous"}

        # 映射needs_confirmation到前端显示的safety_level
        safety_level = "destructive" if needs_confirm else "safe"

        return {
            "is_safe": not needs_confirm,
            "requires_confirmation": needs_confirm,
            "blocked": False,
            "message": "",
            "safety_level": safety_level,
        }

    @staticmethod
    def _get_needs_confirmation(tool_meta, params: Dict) -> bool:
        """获取生效的确认策略：action级 > 工具级"""
        if tool_meta.action_confirmation and params.get("action"):
            return tool_meta.action_confirmation.get(
                params["action"], tool_meta.needs_confirmation
            )
        return tool_meta.needs_confirmation

    @staticmethod
    def _check_known_risks(tool_name: str, params: Dict) -> Optional[Dict]:
        """已知风险检测：路径越权 / 写入污染 / 代码注入"""
        from app.services.tools.registry import tool_registry
        from app.services.tools.tool_types import ToolCategory

        all_categories = tool_registry.get_categories()
        file_tools = set(all_categories.get(ToolCategory.FILE, []))

        if tool_name in file_tools:
            try:
                from app.services.tools.file.file_tools import FileTools
                path = params.get("path") or params.get("source_path") or params.get("target_path") or params.get("file_path") or params.get("directory")
                if path:
                    is_valid, msg = FileTools()._validate_path(path)
                    if not is_valid:
                        return {"is_safe": False, "blocked": True, "message": f"路径越权: {msg}"}
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 路径检查异常,阻止执行: {e}")
                return {"is_safe": False, "blocked": True,
                        "message": f"安全检查异常(已阻止): {e}"}

        if tool_name == _WRITE_RISK_TOOL:
            try:
                from app.services.tools.file.file_tools import FileTools
                file_path = params.get("file_path", "")
                text = params.get("content", "")
                ft = FileTools()
                error, _ = ft._check_write_safety(file_path, text)
                if error:
                    return {"is_safe": False, "blocked": True, "message": f"写入污染: {error}"}
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 写入检查异常,阻止执行: {e}")
                return {"is_safe": False, "blocked": True,
                        "message": f"安全检查异常(已阻止): {e}"}

        fund_runtime_tools = set(all_categories.get(ToolCategory.FUND_RUNTIME, []))
        code_injection_tools = _CODE_INJECTION_RISK_TOOLS & fund_runtime_tools
        if tool_name in code_injection_tools:
            try:
                import re
                from app.services.tools.tool_constants import DANGEROUS_PATTERNS
                code = params.get("command") or params.get("code") or ""
                for pattern_str, desc in DANGEROUS_PATTERNS:
                    if re.search(pattern_str, code):
                        return {"is_safe": False, "blocked": True,
                                "message": f"代码注入: {desc}"}
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 代码注入检查异常,阻止执行: {e}")
                return {"is_safe": False, "blocked": True,
                        "message": f"安全检查异常(已阻止): {e}"}

        return None


_checker: Optional[ToolSafetyChecker] = None


def get_tool_safety_checker() -> ToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = ToolSafetyChecker()
    return _checker



__all__ = ["ToolSafetyChecker", "get_tool_safety_checker"]

