# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #14 fix: 删known_risk.requires_confirmation死分支
# 2026-07-18 小欧 #15/#50 fix: 删SafetyResult.is_safe死字段
# 2026-07-30 - 小欧 - auto_confirm+绕过时仍查needs_confirmation
# 2026-07-31 - 小欧 - 撤销auto_confirm: 恢复security.enabled=false原绕过路径, 删auto_confirm字段
"""
工具安全检查器 — 执行前安全检查（Safety层入口）

Safety层（本文件 + path_safe_check.py）：
  - 路径黑名单/白名单校验（_is_forbidden_path → validate_path）
  - 路径穿越(..)拒绝
  - 写入大小保护
  - 二元安全确认(needs_confirmation)
  - 已知风险检测(路径越权/写入污染)

工具层（validate/file_safety_checker.py + validate/file_path_checker.py + validate/file_type_checker.py）独立运行、互不调用：
  - check_content_safety: 内容安全检查（None/空/null字节/类型/append冲突）
  - validate_path: 非空/保留字符/保留名/系统目录硬阻断/存在性+类型/业务警告
  - check_file_type: 文件类型检查（文本/媒体/文档/压缩）
  - check_tool_module: 依赖库安装检查
  - check_office_file: 路径+类型+模块安全三位一体

Layer 2: 二元安全确认(needs_confirmation)
Layer 3: 已知风险检测(路径越权/写入污染/代码注入)

2026-06-16 小沈 删除5级枚举，改用二元安全+check_fn
2026-06-17 小沈 删除record_operation/execute_with_safety委托(打破tools→safety循环依赖)，
             路径校验改用path_safe_check(打破safety→tools循环依赖)
2026-07-04 小欧 补充两层架构说明注释
2026-07-09 北京老陈 补充validate层完整函数清单
"""


from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.logger import logger
from app.config import get_config
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.services.safety.path_safe_check import validate_tool_path as _validate_tool_path

_WRITE_RISK_TOOL = "writetext"



@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25
    #15 #50 fix: 删 is_safe 死字段(无人消费) — 小欧 2026-07-18"""
    blocked: bool = False
    requires_confirmation: bool = False
    message: str = ""
    safety_level: str = "safe"
    auto_confirm: bool = False


def _is_skip_safety() -> bool:
    """运行时检查安全开关 — 只读 config.yaml security.enabled"""
    try:
        return not get_config().get("security.enabled", True)
    except Exception:
        return False


class ToolSafetyChecker:
    """工具执行前安全检查 — 确认判定 + 已知风险检测"""

    def check_before_execute(self, tool_name: str, params: Optional[Dict] = None) -> SafetyResult:
        """
        执行前安全检查入口（Safety层）
        工具层的 validate_path() 先于本函数执行，已拦截空/保留字符/保留名/系统目录/不存在/类型不匹配
        本函数负责：路径黑名单/白名单/路径穿越/写入大小保护/二元确认

        安全开关: config.yaml security.enabled=false 时跳过所有检查
        """
        if _is_skip_safety():
            tool_meta = tool_registry.get_tool(tool_name)
            if tool_meta:
                needs_confirm = self._get_needs_confirmation(tool_meta, params or {})
                if needs_confirm:
                    return SafetyResult(requires_confirmation=True, auto_confirm=True,
                            blocked=False, message="安全开关已绕过(提示照出)",
                            safety_level="destructive")
            return SafetyResult(requires_confirmation=False,
                    blocked=False, message="安全开关已绕过",
                    safety_level="safe")

        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            return SafetyResult(blocked=True,
                    message=f"工具{tool_name}未注册",
                    safety_level="dangerous")

        known_risk = self._check_known_risks(tool_name, params or {})
        if known_risk is not None:
            # #14 fix: 已知风险只拦截，不触发确认（确认由 needs_confirm 路径驱动）— 小欧 2026-07-18
            known_risk.safety_level = "dangerous"
            return known_risk

        needs_confirm = self._get_needs_confirmation(tool_meta, params or {})

        if tool_meta.check_fn:
            try:
                custom_result = tool_meta.check_fn(params or {})
                if not custom_result.get("is_safe", True):
                    return SafetyResult(
                        blocked=True,
                        message=custom_result.get("message", "安全检查未通过"),
                        safety_level=custom_result.get("safety_level", "dangerous"),
                    )
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] check_fn异常,阻止执行: {e}")
                return SafetyResult(blocked=True,
                        message=f"安全检查异常(已阻止): {e}",
                        safety_level="dangerous")

        safety_level = "destructive" if needs_confirm else "safe"
        return SafetyResult(requires_confirmation=needs_confirm,
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
        """已知风险检测：路径越权 / 写入大小保护 / 代码注入 — 小沈 2026-06-17 改用path_safe_check
        小欧 2026-06-25: 返回SafetyResult替代raw dict
        小欧 2026-06-27: 路径检查委托validate_tool_path(path_safe_check统一处理)"""
        is_valid, msg = _validate_tool_path(tool_name, params)
        if not is_valid:
            return SafetyResult(blocked=True, message=f"路径越权: {msg}")

        if tool_name == _WRITE_RISK_TOOL:
            try:
                # 【#29修复】写入大小保护应优先用path参数（与路径检查一致），file_path兜底 — chendyg 2026-06-26
                file_path = params.get("path") or params.get("file_path", "")
                content = params.get("content", "")
                p = Path(file_path)
                old_size = p.stat().st_size if p.exists() and p.is_file() else 0
                new_size = len(content.encode("utf-8")) if content else 0
                if old_size > 1024 and new_size > 0 and new_size < old_size * 0.20:
                    return SafetyResult(blocked=True,
                            message=f"数据保护:新内容({new_size}字节)远小于原始内容({old_size}字节)")
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 写入检查异常,阻止执行: {e}")
                return SafetyResult(blocked=True, message=f"安全检查异常(已阻止): {e}")


        return None


_checker: Optional[ToolSafetyChecker] = None


def get_tool_safety_checker() -> ToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = ToolSafetyChecker()
    return _checker


__all__ = ["SafetyResult", "ToolSafetyChecker", "get_tool_safety_checker"]
