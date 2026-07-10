# -*- coding: utf-8 -*-
"""
execute_shell_command 分级安全检查 — 独立safety模块

对齐 execute_code_safety.py 设计原则：规则数量>5、规则复杂、规则特殊 → 单独文件

HIGH: blocked=True, 拒绝执行
MEDIUM: requires_confirmation=True, 需用户确认（action_handler.py:70处理确认流程）

— 北京老陈 2026-06-27
— 小健 2026-06-27 迁出到独立safety文件
"""
import re
from typing import Optional

from app.services.safety.tool_safety_checker import SafetyResult
from app.logger import logger


SHELL_DANGEROUS_PATTERNS = [
    # HIGH风险 - 拒绝执行(blocked=True)
    # 组合模式放在单模式之前，便于阅读和维护（MEDIUM仅记录不return，不会降级；HIGH匹配后立即return）
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bRecurse\b.*\bForce\b", "递归+强制删除", "HIGH"),
    (r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\bRecurse\b(?!:\$false\b))", "递归删除目录", "HIGH"),
    (r"Invoke-Command", "远程/本地执行命令", "HIGH"),
    (r"Format-Volume", "格式化卷", "HIGH"),
    (r"Stop-Computer", "关机", "HIGH"),
    (r"Invoke-Expression", "动态执行命令", "HIGH"),
    (r"\bdel\b.*?/s\b", "递归删除文件", "HIGH"),
    (r"\brd\b.*?/s\b", "递归删除目录(rd)", "HIGH"),
    (r"\brmdir\b.*?/s\b", "递归删除目录(rmdir)", "HIGH"),
    (r"(?<!\w)format\b\s+[A-Za-z]:\s*(?:[/\\]|$)", "格式化磁盘", "HIGH"),
    (r"\bshutdown\b(?!\s+[/-]a\b)", "关机/重启", "HIGH"),
    (r"net\s+user\s+\S+.*\/delete", "删除用户", "HIGH"),
    (r"\bcipher\b\s+/w:", "永久数据销毁(cipher /w)", "HIGH"),

    # MEDIUM风险 - 需用户确认(requires_confirmation=True)
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bForce\b", "强制删除文件", "MEDIUM"),
    (r"Restart-Computer", "重启", "MEDIUM"),
    (r"Set-ExecutionPolicy", "修改执行策略", "MEDIUM"),
    (r"Stop-Process\s+.*\bForce\b", "强制停止进程", "MEDIUM"),
    (r"Start-Process", "启动任意进程", "MEDIUM"),
    (r"reg\s+delete", "删除注册表项", "MEDIUM"),
    (r"taskkill\s+/f", "强制杀进程", "MEDIUM"),
]


def check_shell_command_risk(command: str) -> Optional[SafetyResult]:
    """Shell命令风险分级检查 — 仅用于execute_shell_command
    HIGH: blocked=True, 拒绝执行
    MEDIUM: requires_confirmation=True, 需用户确认（action_handler.py:70处理确认流程）
    — 北京老陈 2026-06-27
    — 小健 2026-06-27 迁出到独立safety文件（对齐execute_code_safety.py设计原则）
    """
    medium_hit_desc = None

    # 归一化多行命令为单行，防止 DOTALL 的跨行误匹配 — 小欧 2026-07-05
    # Remove-Item \n -Recurse → Remove-Item -Recurse（仍能正确匹配）
    # 但不再跨行串到无关文本导致假阳性拦截
    normalized = command.replace('\r\n', ' ').replace('\n', ' ')
    for pattern_str, desc, level in SHELL_DANGEROUS_PATTERNS:
        if re.search(pattern_str, normalized, re.IGNORECASE):
            if level == "HIGH":
                return SafetyResult(
                    is_safe=False,
                    blocked=True,
                    message=f"高风险Shell操作: {desc}",
                    safety_level="dangerous",
                )
            elif level == "MEDIUM" and medium_hit_desc is None:
                medium_hit_desc = desc

    if medium_hit_desc:
        logger.warning(f"[Shell安全] 中风险操作: {medium_hit_desc}")
        return SafetyResult(
            is_safe=False,
            blocked=False,
            requires_confirmation=True,
            message=f"中风险Shell操作: {medium_hit_desc}",
            safety_level="destructive",
        )

    return None