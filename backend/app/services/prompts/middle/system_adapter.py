"""
系统信息适配器 - Prompt中间层

【功能】根据服务器操作系统，生成系统自适应的Prompt内容
【核心】服务器OS决定路径格式和命令格式

创建时间: 2026-03-24 17:25:00
作者: 小沈
版本: v1.0
"""
import platform
from typing import Dict, Any
from app.utils.logger import logger


class SystemAdapter:
    """系统信息适配器 - 生成系统自适应的Prompt内容"""
    
    # 路径格式映射
    PATH_FORMATS = {
        "Windows": "C:\\Users\\xxx\\file.txt 或 C:/Users/xxx/file.txt",
        "Linux": "/home/xxx/file.txt",
        "Darwin": "/Users/xxx/file.txt"
    }
    
    # 命令格式映射
    COMMANDS = {
        "Windows": {
            "list": "dir",
            "copy": "copy",
            "move": "move",
            "rename": "ren",
            "delete": "del",
            "delete_dir": "rmdir /s /q",
            "read": "type",
            "create_dir": "mkdir",
            "pwd": "cd",
            "echo": "echo",
            "find_file": "dir /s /b",
            "find_content": "findstr",
            "which": "where",
            "env": "set",
            "ps": "tasklist",
            "kill": "taskkill /F /PID",
            "ping": "ping",
            "netstat": "netstat",
            "ipconfig": "ipconfig",
            "curl": "curl",
            "df": "wmic logicaldisk get size,freespace,caption",
            "chmod": "icacls",
        },
        "Linux": {
            "list": "ls",
            "copy": "cp",
            "move": "mv",
            "rename": "mv",
            "delete": "rm",
            "delete_dir": "rm -rf",
            "read": "cat",
            "create_dir": "mkdir",
            "pwd": "pwd",
            "echo": "echo",
            "find_file": "find",
            "find_content": "grep",
            "which": "which",
            "env": "env",
            "ps": "ps aux",
            "kill": "kill",
            "ping": "ping",
            "netstat": "netstat",
            "ipconfig": "ifconfig",
            "curl": "curl",
            "df": "df -h",
            "chmod": "chmod",
        },
        "Darwin": {
            "list": "ls",
            "copy": "cp",
            "move": "mv",
            "rename": "mv",
            "delete": "rm",
            "delete_dir": "rm -rf",
            "read": "cat",
            "create_dir": "mkdir",
            "pwd": "pwd",
            "echo": "echo",
            "find_file": "find",
            "find_content": "grep",
            "which": "which",
            "env": "env",
            "ps": "ps aux",
            "kill": "kill",
            "ping": "ping",
            "netstat": "netstat",
            "ipconfig": "ifconfig",
            "curl": "curl",
            "df": "df -h",
            "chmod": "chmod",
        }
    }
    
    def __init__(self):
        """初始化，获取当前服务器OS"""
        self.system = self._get_system()
    
    def _get_system(self) -> str:
        """获取服务器操作系统"""
        system = platform.system()
        # Darwin -> macOS
        if system == "Darwin":
            return "Darwin"
        return system
    
    def get_system_name(self) -> str:
        """获取系统名称"""
        if self.system == "Darwin":
            return "macOS"
        return self.system
    
    def get_path_format(self) -> str:
        """获取当前系统的路径格式示例"""
        return self.PATH_FORMATS.get(self.system, "/home/xxx/file.txt")
    
    def get_commands(self) -> Dict[str, str]:
        """获取当前系统的命令格式"""
        return self.COMMANDS.get(self.system, self.COMMANDS["Linux"])
    
    def generate_system_prompt(self, include_commands: bool = True) -> str:
        """
        生成系统信息Prompt - 嵌入到工具Prompt的开头
        
        【修复 2026-05-14 小沈】加include_commands参数
        - ShellAgent: include_commands=True（它的工具就是shell，需要命令格式提示）
        - 其他Agent: include_commands=False（避免LLM看到ipconfig/curl暗示后幻觉调execute_shell_command）
        
        Args:
            include_commands: 是否注入【命令格式】段，默认True(保持向后兼容)
        
        Returns:
            格式化的系统信息字符串
        """
        system_name = self.get_system_name()
        path_format = self.get_path_format()
        
        prompt = f"""【当前系统】
{system_name}

【路径格式】
- 当前系统: {path_format}
"""
        if include_commands:
            commands = self.get_commands()
            cmd_lines = "\n".join(f"- {k}: {v}" for k, v in commands.items())
            prompt += f"""
【命令格式】
{cmd_lines}
"""
        
        prompt += """
【路径规则】
- 必须使用绝对路径（禁止相对路径如 ./file.txt）
- 禁止用 ~ 表示家目录
- ❌ 路径中的中文字符必须原样保留，禁止翻译或转换！用户说"E:\\下载\\科幻小说"就用"E:\\下载\\科幻小说"，禁止改成"E:\\download\\sci-fi-novel"
"""
        
        return prompt
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典格式"""
        return {
            "system": self.get_system_name(),
            "path_format": self.get_path_format(),
            "commands": self.get_commands()
        }


def get_system_adapter() -> SystemAdapter:
    """获取系统适配器实例（单例）"""
    return SystemAdapter()


def get_system_prompt(include_commands: bool = True) -> str:
    """快捷函数：获取系统Prompt字符串
    
    【修复 2026-05-14 小沈】加include_commands参数
    - ShellAgent调用时传include_commands=True
    - 其他Agent调用时传include_commands=False（避免LLM幻觉调execute_shell_command）
    """
    adapter = get_system_adapter()
    logger.info(f"[Prompt中间层] get_system_prompt() 被调用, 服务器OS: {adapter.get_system_name()}, include_commands={include_commands}")
    return adapter.generate_system_prompt(include_commands=include_commands)


if __name__ == "__main__":
    # 测试
    adapter = SystemAdapter()
    print(f"当前系统: {adapter.get_system_name()}")
    print(f"路径格式: {adapter.get_path_format()}")
    print(f"命令: {adapter.get_commands()}")
    print("\n生成的Prompt:")
    print(adapter.generate_system_prompt())