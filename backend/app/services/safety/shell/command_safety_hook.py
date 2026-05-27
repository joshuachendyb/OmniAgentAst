# -*- coding: utf-8 -*-
"""
Shell安全检查Hook — 将CommandParser分析层适配为SafetyHook接口

【小健 2026-05-27】2.28安全检查入口统一：
CommandParser是"分析层"安全（评分+解析），适配为SafetyHook后
可通过SafetyManager.check("shell", action, params)统一调度。

设计原则：
- ISP：CommandSafetyHook只实现check()，不实现execute_with_safety()
  （shell命令不需要备份/回滚等执行层安全）
- OCP：CommandParser本身不变，适配器模式包装
"""
from typing import Any, Dict, Optional

from app.services.safety.manager import SafetyHook
from app.services.command_parser.parser import CommandParser, get_command_parser


class CommandSafetyHook(SafetyHook):
    """Shell命令安全检查Hook — 适配CommandParser为SafetyHook接口"""

    def __init__(self, parser: Optional[CommandParser] = None):
        self._parser = parser or get_command_parser()

    def check(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """安全检查：解析命令语义，返回风险评分

        Args:
            action: 命令/操作名称
            params: 操作参数（应含"command"键）

        Returns:
            {"is_safe": bool, "risk_score": float, "message": str, "semantics": dict}
        """
        command = params.get("command", action)
        semantics = self._parser.parse(command)

        operation = semantics.get("operation", "unknown")
        direction = semantics.get("direction", "unknown")

        DANGER_OPERATIONS = {"delete", "move", "update"}
        risk_score = 0.8 if operation in DANGER_OPERATIONS else 0.3
        is_safe = direction != "write" or operation not in DANGER_OPERATIONS

        return {
            "is_safe": is_safe,
            "risk_score": risk_score,
            "message": f"命令操作: {operation}, 方向: {direction}" if not is_safe else "",
            "semantics": semantics,
        }


_shell_safety_hook: Optional[CommandSafetyHook] = None


def get_shell_safety_hook() -> CommandSafetyHook:
    """获取CommandSafetyHook单例"""
    global _shell_safety_hook
    if _shell_safety_hook is None:
        _shell_safety_hook = CommandSafetyHook()
    return _shell_safety_hook
