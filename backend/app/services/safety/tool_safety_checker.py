# -*- coding: utf-8 -*-
"""
工具安全检查器 — 执行前安全检查

Layer 2: 二元安全确认(needs_confirmation)
Layer 3: 已知风险检测(路径越权/写入污染/代码注入)

2026-06-16 小沈 删除5级枚举，改用二元安全+check_fn
2026-06-17 小沈 删除record_operation/execute_with_safety委托(打破tools→safety循环依赖),
             路径校验改用path_validator(打破safety→tools循环依赖)
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.utils.logger import logger
from app.services.safety.path_validator import validate_tool_path as _validate_tool_path

_WRITE_RISK_TOOL = "write_text_file"
_CODE_INJECTION_RISK_TOOLS = {"execute_shell_command", "execute_code"}


@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25"""
    is_safe: bool = True
    blocked: bool = False
    requires_confirmation: bool = False
    message: str = ""
    safety_level: str = "safe"


def _is_skip_safety() -> bool:
    """运行时检查安全开关 — 只读 config.yaml security.enabled"""
    try:
        from app.config import get_config
        return not get_config().get("security.enabled", True)
    except Exception:
        return False


class ToolSafetyChecker:
    """工具执行前安全检查 — 确认判定 + 已知风险检测"""

    def check_before_execute(self, tool_name: str, params: Optional[Dict] = None) -> SafetyResult:
        """
        执行前安全检查入口

        安全开关: config.yaml security.enabled=false 时跳过所有检查
        """
        if _is_skip_safety():
            return SafetyResult(is_safe=True, requires_confirmation=False,
                    blocked=False, message="安全开关已绕过",
                    safety_level="safe")

        from app.tools.registry import tool_registry

        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            return SafetyResult(is_safe=False, blocked=True,
                    message=f"工具{tool_name}未注册",
                    safety_level="dangerous")

        known_risk = self._check_known_risks(tool_name, params or {})
        if known_risk is not None and not known_risk.is_safe:
            known_risk.safety_level = "dangerous"
            return known_risk

        needs_confirm = self._get_needs_confirmation(tool_meta, params or {})

        if tool_meta.check_fn:
            try:
                custom_result = tool_meta.check_fn(params or {})
                if not custom_result.get("is_safe", True):
                    return SafetyResult(
                        is_safe=False, blocked=True,
                        message=custom_result.get("message", "安全检查未通过"),
                        safety_level=custom_result.get("safety_level", "dangerous"),
                    )
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] check_fn异常,阻止执行: {e}")
                return SafetyResult(is_safe=False, blocked=True,
                        message=f"安全检查异常(已阻止): {e}",
                        safety_level="dangerous")

        safety_level = "destructive" if needs_confirm else "safe"
        return SafetyResult(is_safe=not needs_confirm, requires_confirmation=needs_confirm,
                blocked=False, message="", safety_level=safety_level)

    @staticmethod
    def _get_needs_confirmation(tool_meta, params: Dict) -> bool:
        """获取生效的确认策略：action级 > 工具级"""
        if tool_meta.action_confirmation and params.get("action"):
            return tool_meta.action_confirmation.get(
                params["action"], tool_meta.needs_confirmation
            )
        return tool_meta.needs_confirmation

    @staticmethod
    def _check_known_risks(tool_name: str, params: Dict) -> Optional["SafetyResult"]:
        """已知风险检测：路径越权 / 写入大小保护 / 代码注入 — 小沈 2026-06-17 改用path_validator
        小欧 2026-06-25: 返回SafetyResult替代raw dict
        小欧 2026-06-27: 路径检查委托validate_tool_path(path_validator统一处理)"""
        is_valid, msg = _validate_tool_path(tool_name, params)
        if not is_valid:
            return SafetyResult(is_safe=False, blocked=True, message=f"路径越权: {msg}")

        from app.tools.tool_types import ToolCategory

        if tool_name == _WRITE_RISK_TOOL:
            try:
                from pathlib import Path as _Path
                # 【#29修复】写入大小保护应优先用path参数（与路径检查一致），file_path兜底 — chendyg 2026-06-26
                file_path = params.get("path") or params.get("file_path", "")
                content = params.get("content", "")
                p = _Path(file_path)
                old_size = p.stat().st_size if p.exists() and p.is_file() else 0
                new_size = len(content.encode("utf-8")) if content else 0
                if old_size > 1024 and new_size > 0 and new_size < old_size * 0.20:
                    return SafetyResult(is_safe=False, blocked=True,
                            message=f"数据保护:新内容({new_size}字节)远小于原始内容({old_size}字节)")
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 写入检查异常,阻止执行: {e}")
                return SafetyResult(is_safe=False, blocked=True, message=f"安全检查异常(已阻止): {e}")

        from app.tools.registry import tool_registry
        shell_tools = set(tool_registry.get_categories().get(ToolCategory.SHELL, []))
        # 小健 2026-06-26: 修复P0-4 代码注入检查仅对_CODE_INJECTION_RISK_TOOLS交集生效的bug，改为覆盖所有shell工具
        if tool_name in shell_tools:
            try:
                from app.tools.tool_constants import DANGEROUS_PATTERNS
                code = params.get("command") or params.get("code") or ""
                for pattern_str, desc in DANGEROUS_PATTERNS:
                    if re.search(pattern_str, code):
                        return SafetyResult(is_safe=False, blocked=True, message=f"代码注入: {desc}")
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 代码注入检查异常,阻止执行: {e}")
                return SafetyResult(is_safe=False, blocked=True, message=f"安全检查异常(已阻止): {e}")

        return None


_checker: Optional[ToolSafetyChecker] = None


def get_tool_safety_checker() -> ToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = ToolSafetyChecker()
    return _checker


__all__ = ["SafetyResult", "ToolSafetyChecker", "get_tool_safety_checker"]
