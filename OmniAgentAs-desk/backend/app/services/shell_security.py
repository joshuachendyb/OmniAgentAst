# Shell命令黑名单安全检查服务
# 编程人：小沈
# 创建时间：2026-02-17

"""
Shell命令黑名单安全检查服务
提供命令安全性检查，识别危险操作
"""

import re
from typing import Tuple, List, Optional
from app.utils.logger import logger


# ============================================================
# Shell命令黑名单安全规则定义
# 编程人：小沈
# 创建时间：2026-02-17
# 最后更新：2026-02-18
#
# 安全规则分类：
# 1. 系统破坏类 - 递归删除、格式化磁盘
# 2. 权限提升类 - sudo、su、chmod
# 3. 网络攻击类 - 反向shell、端口扫描
# 4. 数据泄露类 - 读取敏感文件
# 5. 进程终止类 - 强制终止进程
# 6. 系统关键目录类 - Windows/Linux系统目录
# ============================================================

# 危险命令黑名单
DANGEROUS_COMMANDS = [
    # ====== 1. 系统破坏类 - 递归删除 ======
    'rm -rf /', 'rm -rf /*', 'rm -rf .', 'rm -rf *',
    'rm -rf /bin', 'rm -rf /usr', 'rm -rf /etc', 'rm -rf /home',
    'rm -rf /root', 'rm -rf /var', 'rm -rf /tmp',
    'rmdir /', 'rmdir /*', 'rmdir .', 'rmdir /etc',
    'del /f /s /q', 'deltree /', 'rd /s /q',
    'rm -rf $HOME', 'rm -rf ~',
    
    # ====== 2. 磁盘格式化类 ======
    'format', 'format c:', 'format d:', 'format e:',
    'mkfs', 'mkfs.ext4', 'mkfs.ext3', 'mkfs.ntfs',
    'mkfs.vfat', 'mkfs.fat', 'newfs',
    'dd if=/dev/zero', 'dd if=/dev/urandom', 'dd of=/dev/sda',
    'shred -n', 'shred -z',
    
    # ====== 3. 权限提升类 ======
    'sudo', 'sudo -i', 'sudo -s', 'sudo su',
    'su -', 'su root', 'su -root',
    'chmod 777 /', 'chmod -R 777', 'chmod 000',
    'chown -R', 'chown root:root',
    'setfacl -R', 'acl -R',
    
    # ====== 4. 网络攻击类 ======
    'nc -e', 'ncat -e', 'netcat -e',
    'bash -i', 'sh -i', '/bin/sh -i',
    '/dev/tcp/', '/dev/udp/',
    'curl -X', 'wget -O-', 'lynx',
    'nmap', 'nikto', 'sqlmap',
    'nc -l -p', 'nc -lvnp',
    
    # ====== 5. 数据泄露类 - 读取敏感文件 ======
    # Linux敏感文件
    'cat /etc/passwd', 'cat /etc/shadow', 'cat /etc/hosts',
    'cat /etc/sudoers', 'cat /etc/group',
    'cat ~/.ssh/id_rsa', 'cat ~/.ssh/authorized_keys',
    'cat /var/log/', 'tail /etc/passwd',
    # Windows敏感文件
    'type C:\\Windows\\System32\\drivers\\etc\\hosts',
    'type C:\\Windows\\System32\\config\\SAM',
    'type C:\\Windows\\System32\\config\\SYSTEM',
    'powershell Get-Content C:\\',
    'reg query HKLM\\',
    
    # 中文危险命令
    '读取密码', '读取shadow', '查看密码', '查看shadow',
    '获取密码', '获取shadow', '格式化硬盘', '格式化磁盘',
    '删除所有', '删除全部', '清除硬盘', '清除磁盘',
    
    # ====== 6. 进程终止类 ======
    'kill -9 -1', 'taskkill /f /im',
    'pkill -9', 'killall -9', 'killall',
    'taskkill /im explorer.exe',
    'shutdown -r now', 'shutdown -h now',
    'reboot', 'init 6', 'init 0',
    
    # ====== 7. 系统关键目录危险操作 ======
    # 注意：仅禁止在系统目录上执行危险操作，不是禁止访问
    # Windows危险操作
    'del C:\\Windows\\System32', 'rd /s /q C:\\Windows',
    'icacls C:\\Windows',
    # Linux危险操作
    'chmod -R /bin', 'chmod -R /sbin',
    'chown -R /etc',
]

# 系统关键目录列表（用于模式匹配）
SYSTEM_CRITICAL_DIRS = {
    # Windows
    'C:\\Windows', 'C:\\Windows\\System32', 'C:\\Windows\\SysWOW64',
    'C:\\Program Files', 'C:\\Program Files (x86)',
    'C:\\Users\\Public', 'C:\\Recovery',
    # Linux
    '/bin', '/sbin', '/usr/bin', '/usr/sbin',
    '/lib', '/lib64', '/etc', '/sys',
    '/proc', '/dev', '/boot', '/root',
    '/var', '/opt', '/srv',
}


# ============================================================
# CRSS评分系统常量定义 (设计文档v1.1)
# ============================================================

# 操作类型权重表（维度1）
OPERATION_WEIGHTS = {
    'READ': {'min': 0, 'max': 2, 'default': 1, 'keywords': ['cat', 'ls', 'grep', '查看', '读取', 'type', 'dir']},
    'CREATE': {'min': 2, 'max': 4, 'default': 3, 'keywords': ['mkdir', 'touch', '创建', '新建', 'md']},
    'UPDATE': {'min': 4, 'max': 7, 'default': 5, 'keywords': ['edit', 'sed', '修改', '编辑', '更新', 'echo', 'write']},
    'DELETE': {'min': 6, 'max': 10, 'default': 8, 'keywords': ['rm', 'del', '删除', 'remove', '清除', 'rmdir', 'rd']},
    'EXEC': {'min': 5, 'max': 10, 'default': 7, 'keywords': ['sudo', 'run', 'exec', '执行', '运行', 'start']},
}

# 操作对象权重表（维度2）
TARGET_WEIGHTS = {
    'TEMP': {'min': 0, 'max': 4, 'default': 3, 'patterns': [r'\.tmp$', r'\.cache', r'^temp[/\\]', r'temp[/\\]', r'\.log$', r'log[/\\]', r'\*.tmp']},
    'USER': {'min': 3, 'max': 5, 'default': 4, 'patterns': [r'~/', r'/home/', r'文档[/\\]', r'用户', r'documents', r'users?[/\\]']},
    'PROJECT': {'min': 3, 'max': 6, 'default': 3, 'patterns': [r'src[/\\]', r'app[/\\]', r'backend[/\\]', r'frontend[/\\]', r'\.py', r'\.js', r'\.ts', r'tests[/\\]', r'config[/\\]', r'\.git']},
    'SYSTEM': {'min': 8, 'max': 10, 'default': 9, 'patterns': [r'C:\\Windows', r'/bin', r'/etc', r'/sbin', r'/usr', r'系统', r'windows[/\\]system32', r'registry']},
}

# 本项目(OmniAgentAs-desk)保护目录列表
PROJECT_PROTECTED_DIRS = [
    'backend/', 'frontend/', 'config/', 'tests/', 
    'doc-阶段2.1/', 'notes/', 'src/', '.git/',
    'package.json', 'requirements.txt', 'version.txt'
]

# 影响范围系数（维度3）
SCOPE_MULTIPLIERS = {
    'SINGLE_FILE': 1.1,     # 单文件：具体文件名，如 tests/11.txt 或 *.tmp
    'DIRECTORY': 1.45,      # 目录：目录名/结尾，如 tests/ 或 src/
    'CROSS_DIR': 1.5,        # 跨目录：包含通配符，如 tests/*.txt
    'SYSTEM': 3.0,           # 系统级：-rf, /s /q, /
}

# 范围识别关键词
SCOPE_PATTERNS = {
    'SINGLE_FILE': [r'^[^*?]+\.[a-zA-Z0-9]+$', r'^[^*?/]+$'],  # 具体文件名
    'DIRECTORY': [r'[/\\]$', r'\$'],                              # 以/或\结尾
    # 只匹配明确的全盘操作，不匹配普通通配符
    'CROSS_DIR': [r'所有', r'批量', r'全部'],
    # 只匹配真正的系统级操作
    'SYSTEM': [r'/s\s+/q', r'^[/\\]$', r'根目录', r'全盘'],
}


# ============================================================
# 危险命令模式（正则表达式）- 用于更灵活的匹配
# ============================================================
DANGEROUS_PATTERNS = [
    # ====== 递归删除模式 ======
    # 只匹配系统根目录（/ 或 /*），不匹配普通目录如 temp/, src/
    r'rm\s+-[rf]+\s+/\s*$',              # rm -rf / (根目录)
    r'rm\s+-[rf]+\s+/\*\s*$',            # rm -rf /* (根目录下所有)
    r'rm\s+-[rf]+\s+/(bin|usr|etc|home|root|var|tmp|sbin|sys|proc|dev|boot|opt|srv)\s*$',  # rm -rf /bin
    r'rmdir\s+/\s*$',                     # rmdir / (根目录)
    r'rmdir\s+/\*\s*$',                   # rmdir /*
    r'rmdir\s+/(bin|usr|etc|home|root|var|tmp|sbin|sys|proc|dev|boot|opt|srv)\s*$',  # rmdir /bin
    r'del\s+/s\s+/q',                    # del /s /q (系统级递归删除)
    
    # ====== 格式化磁盘模式 ======
    r'format\s+[a-zA-Z]:?',              # format C:
    r'mkfs\.',                           # mkfs.xxx
    r'newfs\s+',                         # newfs (BSD)
    r'shred\s+-[nzu]',                   # shred -n -z -u
    
    # ====== dd写入设备模式 ======
    r'dd\s+.*of=/dev/',                  # dd of=/dev/sdX
    r'dd\s+if=/dev/zero',               # dd if=/dev/zero
    
    # ====== 权限提升模式 ======
    r'sudo\s+',                          # sudo anything
    r'su\s+-\s*root',                    # su -root
    r'chmod\s+777\s+[/\\]',              # chmod 777 /
    r'chmod\s+-R\s+777',                 # chmod -R 777
    r'chown\s+-R',                       # chown -R
    
    # ====== 网络攻击模式 ======
    r'nc\s+-[elvp]\s+',                  # nc -e, nc -l
    r'ncat\s+-e\s+',                     # ncat -e
    r'bash\s+-i',                        # bash -i
    r'sh\s+-i',                          # sh -i
    r'/dev/tcp/',                        # /dev/tcp/host/port
    r'nmap\s+',                          # nmap扫描
    r'sqlmap\s+',                        # SQL注入
    
    # ====== 读取敏感文件模式 ======
    r'cat\s+/etc/passwd',                # 读取用户列表
    r'cat\s+/etc/shadow',                # 读取密码哈希
    r'cat\s+/etc/sudoers',               # 读取sudo配置
    r'type\s+C:\\Windows\\System32\\drivers\\etc\\hosts',
    r'type\s+C:\\Windows\\System32\\config\\SAM',
    r'Get-Content\s+C:\\Windows',
    r'reg\s+query\s+HKLM\\',
    
    # ====== 进程终止模式 ======
    r'kill\s+-9\s+-1',                   # kill -9 -1 (终止所有进程)
    r'taskkill\s+/f\s+/im\s+\*',         # taskkill /f /im *
    r'pkill\s+-9',                       # pkill -9
    r'killall\s+-9',                      # killall -9
    r'shutdown\s+',                      # shutdown命令
    r'reboot\s+',                        # reboot命令
    r'init\s+[06]',                      # init 0/6
    
    # ====== 系统目录操作模式 ======
    r'cd\s+C:\\Windows\\System32',
    r'cd\s+/bin', r'cd\s+/sbin',
    r'cd\s+/etc', r'cd\s+/proc',
    r'chmod\s+-R\s+[/\\]bin',
    r'chown\s+-R\s+[/\\]etc',
    
    # ====== 下载执行模式 ======
    r'curl.*\|\s*(sh|bash|python)',
    r'wget.*\|\s*(sh|bash|python)',
    r'powershell.*-enc\b',               # PowerShell编码命令
    r'powershell.*-e\b',                 # PowerShell -e简短参数
    r'cmd\s+/c\s+.*\|',                  # cmd | sh
    
    # ====== 持久化操作模式 ======
    r'crontab\s+-r',                     # 删除crontab
    r'service\s+.*\s+stop',
    r'systemctl\s+kill',
    r'reg\s+add\s+HKEY',                # Windows注册表添加
    r'reg\s+delete\s+HKEY',              # Windows注册表删除
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
    
    def check_system_dirs(self, command: str) -> Tuple[bool, str]:
        """
        检查命令是否操作了系统关键目录
        
        Args:
            command: 待检查的命令
            
        Returns:
            Tuple[bool, str]: (是否安全, 警告信息)
        """
        if not command:
            return True, ""
        
        command_lower = command.lower()
        
        # 检查是否操作了系统关键目录
        for critical_dir in SYSTEM_CRITICAL_DIRS:
            # 检查目录路径是否在命令中
            if critical_dir.lower() in command_lower:
                # 进一步检查是否是危险操作
                dangerous_ops = ['rm', 'del', 'rd', 'rmdir', 'format', 'mkfs', 'chmod', 'chown', 'icacls']
                if any(op in command_lower for op in dangerous_ops):
                    logger.warning(f"检测到系统关键目录操作: {critical_dir}")
                    return False, f"禁止操作系统关键目录: {critical_dir}"
                else:
                    logger.warning(f"警告: 访问系统关键目录: {critical_dir}")
                    return False, f"警告: 访问系统关键目录可能存在风险: {critical_dir}"
        
        return True, ""


# 全局实例
_safety_checker: Optional[CommandSafetyChecker] = None


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


# ============================================================
# CRSS评分系统解析函数 (设计文档v1.1)
# ============================================================

def parse_operation_type(command: str) -> str:
    """
    解析操作类型
    
    按优先级检查：DELETE > EXEC > UPDATE > CREATE > READ
    避免 READ 的通用关键词（如dir）误匹配其他操作
    
    Args:
        command: 待解析的命令
        
    Returns:
        str: 操作类型 (READ/CREATE/UPDATE/DELETE/EXEC)
    """
    command_lower = command.lower().strip()
    
    # 按优先级检查（先检查具体的操作，避免子串误匹配）
    priority_order = ['DELETE', 'EXEC', 'UPDATE', 'CREATE']
    
    for op_type in priority_order:
        for keyword in OPERATION_WEIGHTS[op_type]['keywords']:
            if keyword.lower() in command_lower:
                return op_type
    
    # 最后检查 READ（因为 READ 包含 dir 等通用子串）
    for keyword in OPERATION_WEIGHTS['READ']['keywords']:
        if keyword.lower() in command_lower:
            return 'READ'
    
    # 默认为读取操作
    return 'READ'


def parse_operation_target(command: str) -> str:
    """
    解析操作对象类型
    
    Args:
        command: 待解析的命令
        
    Returns:
        str: 对象类型 (TEMP/USER/PROJECT/SYSTEM)
    """
    command_lower = command.lower().strip()
    
    # 按优先级检查（从高到低）
    # 系统级最危险，优先检查
    for target_type, config in TARGET_WEIGHTS.items():
        for pattern in config['patterns']:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return target_type
    
    # 默认为用户数据
    return 'USER'


def parse_impact_scope(command: str) -> str:
    """
    解析影响范围
    
    Args:
        command: 待解析的命令
        
    Returns:
        str: 范围类型 (SINGLE_FILE/DIRECTORY/CROSS_DIR/SYSTEM)
    """
    command_lower = command.lower().strip()
    
    # 检查系统级（最危险）
    for pattern in SCOPE_PATTERNS['SYSTEM']:
        if re.search(pattern, command_lower):
            return 'SYSTEM'
    
    # 检查跨目录
    for pattern in SCOPE_PATTERNS['CROSS_DIR']:
        if re.search(pattern, command_lower):
            return 'CROSS_DIR'
    
    # 检查目录
    for pattern in SCOPE_PATTERNS['DIRECTORY']:
        if re.search(pattern, command_lower):
            return 'DIRECTORY'
    
    # 默认为单文件
    return 'SINGLE_FILE'


def calculate_risk_score(command: str) -> int:
    """
    计算命令风险分数 (CRSS评分系统)
    
    计算公式: (操作类型权重 + 操作对象权重) / 2 × 影响范围系数
    分数范围: 0-10
    
    Args:
        command: 待检查的命令
        
    Returns:
        int: 风险分数 (0=安全, 10=极度危险)
    """
    if not command or not command.strip():
        return 0
    
    command_lower = command.lower().strip()
    
    # 1. 黑名单命令直接10分（致命危险）
    checker = get_safety_checker()
    if not checker.is_safe(command):
        return 10
    
    # 2. 解析三个维度
    op_type = parse_operation_type(command)
    op_target = parse_operation_target(command)
    scope = parse_impact_scope(command)
    
    # 3. 获取各维度权重
    type_score = OPERATION_WEIGHTS[op_type]['default']
    target_score = TARGET_WEIGHTS[op_target]['default']
    scope_multiplier = SCOPE_MULTIPLIERS[scope]
    
    # 4. 计算总分（按设计文档公式）
    raw_score = (type_score + target_score) / 2 * scope_multiplier
    final_score = min(10, int(round(raw_score)))
    
    logger.info(f"CRSS评分: command='{command}', type={op_type}({type_score}), target={op_target}({target_score}), scope={scope}(×{scope_multiplier}), score={final_score}")
    
    return final_score


def get_risk_message(score: int, command: str = "") -> str:
    """
    根据风险分数获取提示信息
    
    按设计文档v1.1返回标准化提示信息
    
    Args:
        score: 风险分数 (0-10)
        command: 命令（可选）
        
    Returns:
        str: 用户可见的提示信息
    """
    if score <= 3:
        return "操作安全"
    elif score <= 6:
        return "操作存在风险，请注意"
    elif score <= 8:
        return "检测到风险操作，是否确认？"
    else:
        return "危险操作已被系统拦截"
