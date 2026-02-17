# Shell命令黑名单安全检查服务
# 编程人：小沈
# 创建时间：2026-02-17

"""
Shell命令黑名单安全检查服务
提供命令安全性检查，识别危险操作
"""

import re
from typing import Tuple, List
from app.utils.logger import logger


# 危险命令黑名单
DANGEROUS_COMMANDS = [
    # 系统破坏类 - 递归删除
    'rm -rf /', 'rm -rf /*', 'rm -rf .', 'rm -rf *',
    'rmdir /', 'rmdir /*', 'rmdir .',
    'del /f /s /q', 'deltree /', 'rd /s /q',
    'format', 'format c:', 'format d:',
    'mkfs', 'mkfs.ext4', 'mkfs.ntfs',
    'dd if=/dev/zero', 'dd if=/dev/urandom',
    
    # 权限提升类
    'sudo', 'su -', 'su root', 'chmod 777 /',
    'chown -R', 'chmod -R 777',
    
    # 网络攻击类
    'nc -e', 'ncat -e', 'netcat -e',
    'bash -i', 'sh -i', '/bin/sh -i',
    'curl -X', 'wget -O-', 'lynx',
    
    # 数据泄露类
    'cat /etc/passwd', 'cat /etc/shadow',
    'cat /etc/hosts', 'type C:\\Windows\\System32\\drivers\\etc\\hosts',
    
    # 进程终止类
    'kill -9 -1', 'taskkill /f /im',
    'pkill -9', 'killall -9',
    
    # 修改系统配置
    'sysctl -w', 'echo > /proc/',
    'reg add', 'reg delete',
]


# 危险命令模式（正则表达式）
DANGEROUS_PATTERNS = [
    # 递归删除根目录
    r'rm\s+-[rf]+\s+[/\\*]+',
    r'rmdir\s+[/\\*]+',
    
    # 格式化磁盘
    r'format\s+[a-zA-Z]:?',
    r'mkfs\.',
    
    # dd写入设备
    r'dd\s+.*of=/dev/',
    
    # 权限提升
    r'sudo\s+',
    r'su\s+-\s*root',
    r'chmod\s+777\s+[/\\]',
    
    # 网络反向shell
    r'nc\s+-e\s+',
    r'ncat\s+-e\s+',
    r'bash\s+-i',
    r'sh\s+-i',
    
    # 读取敏感文件
    r'cat\s+/etc/passwd',
    r'cat\s+/etc/shadow',
    r'type\s+C:\\Windows\\System32\\drivers\\etc\\hosts',
    
    # 强制终止所有进程
    r'kill\s+-9\s+-1',
    r'taskkill\s+/f\s+/im\s+\*',
    r'pkill\s+-9',
    r'killall\s+-9',
    
    # 修改注册表（Windows）
    r'reg\s+(add|delete)\s+HKEY',
    
    # 下载执行
    r'curl.*\|\s*sh',
    r'wget.*\|\s*sh',
    r'powershell.*-enc',
]


class CommandSafetyChecker:
    """
    命令安全检查器
    检查命令是否包含危险操作
    """
    
    def __init__(self):
        """初始化检查器"""
        # 编译正则表达式模式
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in DANGEROUS_PATTERNS
        ]
        logger.info("CommandSafetyChecker 初始化完成")
    
    def check(self, command: str) -> Tuple[bool, str]:
        """
        检查命令是否安全
        
        Args:
            command: 待检查的命令
            
        Returns:
            Tuple[bool, str]: (是否安全, 危险原因)
        """
        if not command:
            return True, ""
        
        command_lower = command.lower().strip()
        
        # 检查黑名单命令
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command_lower:
                logger.warning(f"检测到危险命令: {dangerous}")
                return False, f"检测到危险命令: {dangerous}"
        
        # 检查危险模式
        for pattern in self._compiled_patterns:
            match = pattern.search(command)
            if match:
                logger.warning(f"检测到危险命令模式: {match.group()}")
                return False, f"检测到危险命令模式: {match.group()}"
        
        return True, ""
    
    def is_safe(self, command: str) -> bool:
        """
        快速检查命令是否安全
        
        Args:
            command: 待检查的命令
            
        Returns:
            bool: 是否安全
        """
        is_safe, _ = self.check(command)
        return is_safe
    
    def get_risk_level(self, command: str) -> str:
        """
        获取命令风险等级
        
        Args:
            command: 待检查的命令
            
        Returns:
            str: 风险等级 (safe/low/medium/high/critical)
        """
        is_safe, reason = self.check(command)
        
        if is_safe:
            return "safe"
        
        # 根据危险原因判断风险等级
        reason_lower = reason.lower()
        
        if any(keyword in reason_lower for keyword in ['rm -rf', 'format', 'mkfs', 'dd if']):
            return "critical"
        elif any(keyword in reason_lower for keyword in ['kill -9', 'sudo', 'su', 'chmod 777']):
            return "high"
        elif any(keyword in reason_lower for keyword in ['nc -e', 'ncat', 'bash -i', 'reg add']):
            return "high"
        else:
            return "medium"


# 全局实例
_safety_checker: CommandSafetyChecker = None


def get_safety_checker() -> CommandSafetyChecker:
    """获取安全检查器实例"""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = CommandSafetyChecker()
    return _safety_checker


def check_command_safety(command: str) -> Tuple[bool, str]:
    """
    快速检查命令安全性
    
    Args:
        command: 待检查的命令
        
    Returns:
        Tuple[bool, str]: (是否安全, 危险原因)
    """
    checker = get_safety_checker()
    return checker.check(command)


def is_command_safe(command: str) -> bool:
    """
    快速检查命令是否安全
    
    Args:
        command: 待检查的命令
        
    Returns:
        bool: 是否安全
    """
    checker = get_safety_checker()
    return checker.is_safe(command)


def get_command_risk_level(command: str) -> str:
    """
    获取命令风险等级
    
    Args:
        command: 待检查的命令
        
    Returns:
        str: 风险等级
    """
    checker = get_safety_checker()
    return checker.get_risk_level(command)
