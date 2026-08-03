
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 删 SafetyResult(is_safe=False) 两处 kwarg: SafetyResult 已于 2026-07-18 删除 is_safe 字段, 此处漏改致中危/destructive shell 命令检查 TypeError 崩溃; 删后 blocked/requires_confirmation/safety_level 已正确表达风险意图, 行为不变
# 2026-07-27 - 小欧 - 补全CMD安全检查模式(diskpart/bcdedit/vssadmin/sc delete等HIGH+med); 所有模式加 # PS / # CMD / # PS+CMD 注释
# 2026-07-27 - 小欧 - Bugfix: MEDIUM多命中合并(原只记录首个); 规则分组优化(PS/CMD/PS+CMD); 注释修正(Remove-Item...Recurse标PS+CMD→PS)
# 2026-07-28 - 小欧 - 欧阳BUG-09修复: 新增shell_type参数; 规则加第4元素st_tag("ps"/"cmd"/None); check_shell_command_risk按shell_type过滤不匹配规则
# 2026-07-28 - 小欧 - 临时目录清理误伤修复: 新增_TEMP_SAFE_PATTERNS+_is_temp_cleanup, Remove-Item类HIGH命中时检查目标路径, 若为已知安全临时目录则降级MEDIUM(日志放行), 非临时路径仍HIGH拦截
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash; 新增6条bash安全规则; 过滤逻辑扩展支持ps7/ps5/bash/cmd; _TEMP_SAFE_PATTERNS扩展bash路径
# 2026-07-31 - 小欧 - Shell池进程保护: 新增_extract_stop_process_pids/_extract_taskkill_pids/_extract_bash_kill_pids; check_shell_command_risk加protected_pids参数; Stop-Process/taskkill/kill命中受保护PID时BLOCKED; 三提取函数+拦截点加日志; message优化为"系统保护进程"避免泄露架构细节
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
    # ═══════════════════════════════════════════════════════════════════
    # HIGH风险 - 拒绝执行(blocked=True)
    # 格式: (pattern, desc, level, shell_type) — shell_type: "ps"/"cmd"/None(双兼容)
    # ═══════════════════════════════════════════════════════════════════
    # ---- PS: PowerShell专属高风险 ----
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bRecurse\b.*\bForce\b", "递归+强制删除", "HIGH", "ps"),
    (r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\bRecurse\b(?!:\$false\b))", "递归删除目录", "HIGH", "ps"),
    (r"Invoke-Command", "远程/本地执行命令", "HIGH", "ps"),
    (r"Format-Volume", "格式化卷", "HIGH", "ps"),
    (r"Stop-Computer", "关机", "HIGH", "ps"),
    (r"Invoke-Expression", "动态执行命令", "HIGH", "ps"),
    # ---- CMD: cmd.exe专属高风险 ----
    (r"\bdiskpart\b", "磁盘分区操作(diskpart)", "HIGH", "cmd"),
    (r"\bbcdedit\b", "引导配置操作(bcdedit)", "HIGH", "cmd"),
    (r"vssadmin\s+delete\s+shadows", "删除卷影副本(vssadmin)", "HIGH", "cmd"),
    (r"\bsc\s+delete\b", "删除服务(sc delete)", "HIGH", "cmd"),
    # ---- PS+CMD: 递归删除/格式化/关机/删除用户/数据销毁 ----
    (r"\bdel\b.*?/s\b", "递归删除文件", "HIGH", None),
    (r"\brd\b.*?/s\b", "递归删除目录(rd)", "HIGH", None),
    (r"\brmdir\b.*?/s\b", "递归删除目录(rmdir)", "HIGH", None),
    (r"(?<!\w)format\b\s+[A-Za-z]:\s*(?:[/\\]|$)", "格式化磁盘", "HIGH", None),
    (r"\bshutdown\b(?!\s+[/-]a\b)", "关机/重启", "HIGH", None),
    (r"net\s+user\s+\S+.*\/delete", "删除用户", "HIGH", None),
    (r"\bcipher\b\s+/w:", "永久数据销毁(cipher /w)", "HIGH", None),
    # ---- bash: bash专属高风险 ----
    (r"\brm\b.*?-rf\s+/", "递归删除(rm -rf /路径)", "HIGH", "bash"),
    (r"\bdd\s+if=.*\sof=/(?:dev/sd|dev/nvme|dev/mmc)", "直接写磁盘(dd)", "HIGH", "bash"),
    (r"\bmkfs\.\w+\s+/dev/", "格式化(ntfs/ext4/xfs)", "HIGH", "bash"),
    (r"\bchmod\s+777\s+/", "修改根目录权限(chmod 777 /)", "HIGH", "bash"),
    (r"\bchown\s+\w+:\w+\s+/", "修改根目录归属(chown : /)", "HIGH", "bash"),

    # ═══════════════════════════════════════════════════════════════════
    # MEDIUM风险 - 需用户确认(requires_confirmation=True)
    # ═══════════════════════════════════════════════════════════════════
    # ---- PS: PowerShell专属中风险 ----
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bForce\b", "强制删除文件", "MEDIUM", "ps"),
    (r"Restart-Computer", "重启", "MEDIUM", "ps"),
    (r"Set-ExecutionPolicy", "修改执行策略", "MEDIUM", "ps"),
    (r"Stop-Process\s+.*\bForce\b", "强制停止进程", "MEDIUM", "ps"),
    (r"Start-Process", "启动任意进程", "MEDIUM", "ps"),
    # ---- CMD: cmd.exe专属中风险 ----
    (r"\bdel\b.*?/f\b", "强制删除文件(del /f)", "MEDIUM", "cmd"),
    (r"\btakeown\b.*?/f\b", "强制获取所有权(takeown /f)", "MEDIUM", "cmd"),
    (r"\bicacls\b.*?/grant\b", "修改文件权限(icacls)", "MEDIUM", "cmd"),
    (r"\bcacls\b.*?/grant\b", "修改文件权限(cacls)", "MEDIUM", "cmd"),
    (r"reg\s+add", "注册表新增/修改(reg add)", "MEDIUM", "cmd"),
    (r"reg\s+import", "导入注册表文件(reg import)", "MEDIUM", "cmd"),
    (r"wmic\s+process\b", "WMIC进程操作(wmic process)", "MEDIUM", "cmd"),
    (r"net\s+(stop|start)\b", "停止/启动服务(net stop/start)", "MEDIUM", "cmd"),
    (r"\bsc\s+(stop|start)\b", "停止/启动服务(sc stop/start)", "MEDIUM", "cmd"),
    (r"\bsc\s+config\b", "修改服务配置(sc config)", "MEDIUM", "cmd"),
    # ---- PS+CMD: 两者共用中风险 ----
    (r"reg\s+delete", "删除注册表项", "MEDIUM", None),
    (r"taskkill\s+/f", "强制杀进程", "MEDIUM", None),
    # ---- bash: bash专属中风险 ----
    (r"\bchmod\s+-R\s+777\b", "递归修改权限(chmod -R 777)", "MEDIUM", "bash"),
    (r"\bkill\b\s", "kill进程(bash)", "MEDIUM", "bash"),
]


# 已知安全临时目录路径模式（用于递归删除误伤降级）
_TEMP_SAFE_PATTERNS = re.compile(
    r'(?i)'
    r'(?:\$env:(?:TEMP|TMP)'                                          # PS: $env:TEMP / $env:TMP
    r'|\$env:LOCALAPPDATA(?:\\Temp|\\Microsoft\\Windows\\INetCache)'  # PS: $env:LOCALAPPDATA\Temp / INetCache
    r'|\\AppData\\Local\\Temp'                                        # 字面路径 \AppData\Local\Temp
    r'|%TEMP%|%TMP%'                                                  # CMD: %TEMP% / %TMP%
    r'|\$TMPDIR|\$TEMP|\$TMP|\$\{TMP\}'                             # bash: $TMPDIR / $TEMP / $TMP / ${TMP}
    r'|/tmp\b'                                                        # bash: unix /tmp
    r')'
)


def _is_temp_cleanup(command: str) -> bool:
    """检查命令是否目标为已知安全临时目录"""
    return bool(_TEMP_SAFE_PATTERNS.search(command))


def _extract_stop_process_pids(command: str) -> set:
    """从 Stop-Process -Id 5092,19128 提取目标PID集合 — 小欧 2026-07-31"""
    m = re.search(r'Stop-Process\s+(?:.*?\s)?-Id\s+([\d,\s]+)', command, re.IGNORECASE)
    if not m:
        return set()
    pids = {int(x) for x in re.split(r'[\s,]+', m.group(1)) if x.isdigit()}
    logger.debug(f"[Shell安全] _extract_stop_process_pids: command={command[:80]}, 提取PID={pids}")
    return pids


def _extract_taskkill_pids(command: str) -> set:
    """从 taskkill /F /PID 5092 提取目标PID集合 — 小欧 2026-07-31"""
    pids = {int(x) for x in re.findall(r'/PID\s+(\d+)', command, re.IGNORECASE)}
    logger.debug(f"[Shell安全] _extract_taskkill_pids: command={command[:80]}, 提取PID={pids}")
    return pids


def _extract_bash_kill_pids(command: str) -> set:
    """从 bash kill 1234 / kill -9 1234 提取目标PID集合 — 小欧 2026-07-31"""
    m = re.search(r'\bkill\b\s+(?:-\d+\s+)*(\d+(?:\s+\d+)*)', command)
    if not m:
        return set()
    pids = {int(x) for x in m.group(1).split()}
    logger.debug(f"[Shell安全] _extract_bash_kill_pids: command={command[:80]}, 提取PID={pids}")
    return pids


def check_shell_command_risk(command: str, shell_type: str = "ps7", protected_pids: Optional[set] = None) -> Optional[SafetyResult]:
    """Shell命令风险分级检查 - HIGH立即拦截, MEDIUM收集合并

    shell_type: "ps7"/"ps5"/"cmd"/"bash" — 过滤不匹配规则; None不过滤
    """
    medium_hits = []
    normalized = command.replace('\r\n', ' ').replace('\n', ' ')
    for pattern_str, desc, level, st_tag in SHELL_DANGEROUS_PATTERNS:
        if st_tag == "ps" and shell_type not in ("ps7", "ps5"):
            continue
        if st_tag == "cmd" and shell_type != "cmd":
            continue
        if st_tag == "bash" and shell_type != "bash":
            continue
        if re.search(pattern_str, normalized, re.IGNORECASE):
            if level == "HIGH":
                # 临时目录清理降级: 递归删除命令(PS Remove-Item / CMD del/rd/rmdir)目标为已知安全临时目录时降为MEDIUM
                # 其他HIGH操作(Format-Volume等)即使命令中包含临时路径也依然拦截 — 小欧 2026-07-28
                if _is_temp_cleanup(normalized) and ('递归' in desc or 'rm -rf' in desc):
                    medium_hits.append(desc)
                    continue
                return SafetyResult(
                    blocked=True,
                    message=f"高风险Shell操作: {desc}",
                    safety_level="dangerous",
                )
            elif level == "MEDIUM" and desc not in medium_hits:
                # Shell池进程保护: Stop-Process/taskkill命中受保护PID时BLOCKED — 小欧 2026-07-31
                if protected_pids:
                    if "强制停止进程" in desc:
                        target_pids = _extract_stop_process_pids(normalized)
                        if target_pids & protected_pids:
                            blocked_pids = target_pids & protected_pids
                            logger.warning(f"[Shell安全] 安全拦截: Stop-Process 目标PID {blocked_pids} 为系统保护进程, 禁止杀死")
                            return SafetyResult(
                                blocked=True,
                                message=f"安全拦截: 目标PID {blocked_pids} 为系统保护进程, 禁止杀死",
                                safety_level="dangerous",
                            )
                    if "强制杀进程" in desc:
                        target_pids = _extract_taskkill_pids(normalized)
                        if target_pids & protected_pids:
                            blocked_pids = target_pids & protected_pids
                            logger.warning(f"[Shell安全] 安全拦截: taskkill 目标PID {blocked_pids} 为系统保护进程, 禁止杀死")
                            return SafetyResult(
                                blocked=True,
                                message=f"安全拦截: 目标PID {blocked_pids} 为系统保护进程, 禁止杀死",
                                safety_level="dangerous",
                            )
                    if "kill进程" in desc:
                        target_pids = _extract_bash_kill_pids(normalized)
                        if target_pids & protected_pids:
                            blocked_pids = target_pids & protected_pids
                            logger.warning(f"[Shell安全] 安全拦截: kill 目标PID {blocked_pids} 为系统保护进程, 禁止杀死")
                            return SafetyResult(
                                blocked=True,
                                message=f"安全拦截: 目标PID {blocked_pids} 为系统保护进程, 禁止杀死",
                                safety_level="dangerous",
                            )
                medium_hits.append(desc)
    if medium_hits:
        combined = "、".join(medium_hits)
        logger.warning(f"[Shell安全] 中风险操作: {combined}")
        return SafetyResult(
            blocked=False,
            requires_confirmation=True,
            message=f"中风险Shell操作: {combined}",
            safety_level="destructive",
        )
    return None

