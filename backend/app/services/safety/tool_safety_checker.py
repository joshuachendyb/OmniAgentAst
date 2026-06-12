# -*- coding: utf-8 -*-
"""
工具安全检查器 — 执行前安全检查

Layer 2: 工具安全级别(read_only/safe/destructive/dangerous_sandbox/dangerous)
Layer 3: 已知风险检测(路径越权/写入污染/代码注入)

Author: 小沈 - 2026-05-27
小沈 - 2026-06-09 删除死代码,语义化命名
"""

import os
from typing import Any, Dict, Optional

from app.utils.logger import logger
from app.services.tools.tool_types import ToolSafetyLevel, DEFAULT_SAFETY_POLICY

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
    """工具执行前安全检查 — 安全级别判定 + 已知风险检测"""

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
            {"is_safe", "risk_score", "safety_level", "requires_confirmation", "blocked", "message"}
        """
        if _is_skip_safety():
            return {"is_safe": True, "risk_score": 0.0, "safety_level": "safe",
                    "requires_confirmation": False, "blocked": False, "message": "安全开关已绕过"}

        from app.services.tools.registry import tool_registry

        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            return {"is_safe": False, "risk_score": 1.0, "message": f"工具{tool_name}未注册", "blocked": True}

        safety_level = self._get_effective_safety_level(tool_meta, params or {})
        policy = DEFAULT_SAFETY_POLICY.get(safety_level, DEFAULT_SAFETY_POLICY[ToolSafetyLevel.SAFE])

        known_risk = self._check_known_risks(tool_name, params or {})
        if known_risk and not known_risk.get("is_safe", True):
            return known_risk

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
    def _get_effective_safety_level(tool_meta, params: Dict) -> ToolSafetyLevel:
        """获取生效的安全级别：action级覆盖 > 工具级默认"""
        if tool_meta.action_safety_map and params.get("action"):
            return tool_meta.action_safety_map.get(params["action"], tool_meta.safety_level)
        return tool_meta.safety_level

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
                        return {"is_safe": False, "risk_score": 1.0, "blocked": True, "message": f"路径越权: {msg}"}
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 路径检查异常,阻止执行: {e}")
                return {"is_safe": False, "risk_score": 1.0, "blocked": True,
                        "message": f"安全检查异常(已阻止): {e}"}

        if tool_name == _WRITE_RISK_TOOL:
            try:
                from app.services.tools.file.file_tools import FileTools
                file_path = params.get("file_path", "")
                text = params.get("content", "")
                ft = FileTools()
                error, _ = ft._check_write_safety(file_path, text)
                if error:
                    return {"is_safe": False, "risk_score": 0.8, "blocked": True, "message": f"写入污染: {error}"}
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 写入检查异常,阻止执行: {e}")
                return {"is_safe": False, "risk_score": 1.0, "blocked": True,
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
                        return {"is_safe": False, "risk_score": 1.0, "blocked": True,
                                "message": f"代码注入: {desc}"}
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 代码注入检查异常,阻止执行: {e}")
                return {"is_safe": False, "risk_score": 1.0, "blocked": True,
                        "message": f"安全检查异常(已阻止): {e}"}

        return None


_checker: Optional[ToolSafetyChecker] = None


def get_tool_safety_checker() -> ToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = ToolSafetyChecker()
    return _checker



__all__ = ["ToolSafetyChecker", "get_tool_safety_checker", "ToolSafetyLevel", "DEFAULT_SAFETY_POLICY"]

