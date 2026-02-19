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
# 危险命令模式（正则表达式）- 用于更灵活的匹配
# ============================================================
DANGEROUS_PATTERNS = [
    # ====== 递归删除模式 ======
    r'rm\s+-[rf]+\s+[/\\*]+',           # rm -rf /
    r'rmdir\s+[/\\*]+',                  # rmdir /
    r'del\s+.*/s\s+/q',                  # del /s /q
    
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

# ============================================================
# 预编译的危险命令模式（提升性能）
# ============================================================
_COMPILED_DANGER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in DANGEROUS_PATTERNS
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
# CRSS (Command Risk Scoring System) 评分系统
# 编程人：小沈
# 创建时间：2026-02-19
# ============================================================

# 操作类型权重表
OPERATION_WEIGHTS = {
    "READ": 1,      # 查询、读取
    "CREATE": 3,    # 创建
    "UPDATE": 5,    # 修改
    "DELETE": 8,    # 删除
    "EXEC": 7,      # 执行
    "BATCH": 9,     # 批量操作
    "UNKNOWN": 2,   # 未识别
}

# 操作对象权重表
TARGET_WEIGHTS = {
    "TEMP": 1,      # 临时数据
    "USER": 4,      # 用户数据
    "PROJECT": 7,   # 项目数据
    "SYSTEM": 10,   # 系统数据
    "UNKNOWN": 2,    # 未识别
}

# 影响范围系数
SCOPE_MULTIPLIERS = {
    "SINGLE_FILE": 1.0,     # 单个文件
    "DIRECTORY": 1.5,        # 整个目录
    "CROSS_DIR": 2.0,        # 跨目录/批量
    "SYSTEM_LEVEL": 3.0,    # 系统级
}

# 操作类型关键词映射
OPERATION_KEYWORDS = {
    "READ": ["cat", "ls", "dir", "pwd", "grep", "find", "head", "tail", "view", "查看", "读取", "查询", "显示"],
    "CREATE": ["mkdir", "touch", "create", "new", "echo", ">", ">>", "创建", "新建", "建立"],
    "UPDATE": ["edit", "sed", "vim", "nano", "modify", "update", "change", "修改", "编辑", "更新", "写入"],
    "DELETE": ["rm", "del", "rmdir", "rd", "unlink", "remove", "delete", "清除", "删除", "清空"],
    "EXEC": ["sudo", "run", "exec", "execute", "start", "运行", "执行", "启动"],
    "BATCH": ["*", "?", "all", "&&", "||", "批量", "全部"],
}

# 对象路径关键词映射
# 注意：扩展名判断必须结合路径上下文，避免误判
TARGET_PATH_KEYWORDS = {
    "TEMP": [".tmp", ".cache", "temp", "temp/", "cache/", ".log", "缓存", "临时"],
    "USER": ["~", "/home/", "/Users/", "文档", "desktop", "download", "用户目录",
             "C:\\Users\\", "C:\\Users\\Public", "D:\\Users\\"],
    "PROJECT": ["src/", "app/", "backend/", "frontend/", "tests/", "config/", "doc-", 
                "项目", "源代码", "workspace", "project"],
    "SYSTEM": ["C:\\Windows", "C:\\Windows\\System32", "C:\\Windows\\SysWOW64",
               "C:\\Program Files", "C:\\Program Files (x86)",
               "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/etc", "/sys",
               "/proc", "/dev", "/lib", "/lib64", "系统", "System32"],
}


def parse_operation_type(command: str) -> str:
    """
    解析命令的操作类型
    
    Args:
        command: 待检查的命令
        
    Returns:
        str: 操作类型 (READ/CREATE/UPDATE/DELETE/EXEC/BATCH/UNKNOWN)
    """
    if not command:
        return "UNKNOWN"
    
    command_lower = command.lower()
    
    # 优先检测批量操作（使用正则精确匹配，避免文件名通配符误判）
    # 只检测真正的批量操作模式：命令链、递归删除等
    batch_patterns = [
        r'&&',           # 命令链
        r'\|\|',         # 条件或
        r';\s*rm\s+',    # ; rm 命令
        r';\s*del\s+',   # ; del 命令
        r'^\s*rm\s+-[rf]+',      # rm -rf 开头（递归删除）
        r'^\s*del\s+/[sq]',      # del /s /q 开头
    ]
    for pattern in batch_patterns:
        if re.search(pattern, command_lower):
            return "BATCH"
    
    # 按优先级检测操作类型
    for op_type, keywords in OPERATION_KEYWORDS.items():
        if any(kw in command_lower for kw in keywords):
            return op_type
    
    return "UNKNOWN"


def parse_operation_target(command: str) -> str:
    """
    解析命令的操作对象类型
    
    Args:
        command: 待检查的命令
        
    Returns:
        str: 对象类型 (TEMP/USER/PROJECT/SYSTEM/UNKNOWN)
    """
    if not command:
        return "UNKNOWN"
    
    command_lower = command.lower()
    
    # 按优先级检测（系统 > 项目 > 用户 > 临时）
    if any(kw in command_lower for kw in TARGET_PATH_KEYWORDS["SYSTEM"]):
        return "SYSTEM"
    
    if any(kw in command_lower for kw in TARGET_PATH_KEYWORDS["PROJECT"]):
        return "PROJECT"
    
    if any(kw in command_lower for kw in TARGET_PATH_KEYWORDS["USER"]):
        return "USER"
    
    if any(kw in command_lower for kw in TARGET_PATH_KEYWORDS["TEMP"]):
        return "TEMP"
    
    return "UNKNOWN"


def parse_impact_scope(command: str) -> str:
    """
    解析命令的影响范围
    
    Args:
        command: 待检查的命令
        
    Returns:
        str: 影响范围 (SINGLE_FILE/DIRECTORY/CROSS_DIR/SYSTEM_LEVEL)
    """
    if not command:
        return "SINGLE_FILE"
    
    command_lower = command.lower().strip()
    
    # 检测系统级操作（必须是在系统路径上下文中）
    # 排除常见的文件路径分隔符误判
    system_patterns = [
        "rm -rf /bin", "rm -rf /usr",
        "rm -rf /etc", "rmdir /", "rd /s /q c:",
    ]
    for pattern in system_patterns:
        if pattern in command_lower:
            return "SYSTEM_LEVEL"
    
    # 专门检测根目录删除（覆盖 "rm -rf /" 和 "rm -rf *"）
    if command_lower.startswith("rm -rf /") or command_lower.startswith("rm -rf *"):
        return "SYSTEM_LEVEL"
    
    # 检测跨目录操作
    if "../" in command_lower or "*" in command_lower:
        # 但如果是文件通配符（如 *.txt），仍是单文件
        if command_lower.endswith("*") or ".txt" in command_lower or ".log" in command_lower:
            return "SINGLE_FILE"
        return "CROSS_DIR"
    
    # 检测目录操作
    if any(kw in command_lower for kw in ["mkdir", "rmdir", "rd /"]):
        return "DIRECTORY"
    
    return "SINGLE_FILE"


def calculate_risk_score(command: str) -> int:
    """
    计算命令的风险分数 (0-10)
    
    公式: (操作分数 + 对象分数) / 2 × 范围系数
    
    注意：如果命令匹配危险命令黑名单，直接返回10分
    
    Args:
        command: 待检查的命令
        
    Returns:
        int: 风险分数 (0-10)
    """
    if not command:
        return 0
    
    # 先检查是否在黑名单中，如果是则直接返回10分
    command_lower = command.lower().strip()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in command_lower:
            return 10
    
    # 检查危险模式（使用预编译的正则提升性能）
    for pattern in _COMPILED_DANGER_PATTERNS:
        if pattern.search(command):
            return 10
    
    # 解析三个维度
    op_type = parse_operation_type(command)
    op_target = parse_operation_target(command)
    scope = parse_impact_scope(command)
    
    # 获取基础分数
    op_score = OPERATION_WEIGHTS.get(op_type, 2)
    target_score = TARGET_WEIGHTS.get(op_target, 2)
    scope_multiplier = SCOPE_MULTIPLIERS.get(scope, 1.0)
    
    # 使用公式计算：(操作分数 + 对象分数) / 2 × 范围系数
    base_score = (op_score + target_score) / 2
    final_score = base_score * scope_multiplier
    
    # 封顶10分
    return min(int(final_score), 10)


def get_risk_message(score: int, command: str = "") -> str:
    """
    根据风险分数生成提示信息
    
    Args:
        score: 风险分数 (0-10)
        command: 命令内容（可选）
        
    Returns:
        str: 提示信息
    """
    if score <= 2:
        return "🟢 安全操作，直接执行"
    elif score <= 4:
        return "🟡 低风险操作，执行并记录日志"
    elif score <= 6:
        return "🟡 中等风险操作，执行并提示用户"
    elif score <= 8:
        return "🟠 较高风险操作，需要用户确认"
    else:
        return "🔴 危险操作，已被系统拦截"


# 导出接口供外部调用
__all__ = [
    "check_command_safety",
    "is_command_safe", 
    "get_command_risk_level",
    "CommandSafetyChecker",
    "get_safety_checker",
    # CRSS评分系统
    "calculate_risk_score",
    "get_risk_message",
    "parse_operation_type",
    "parse_operation_target",
    "parse_impact_scope",
    "OPERATION_WEIGHTS",
    "TARGET_WEIGHTS",
    "SCOPE_MULTIPLIERS",
]
