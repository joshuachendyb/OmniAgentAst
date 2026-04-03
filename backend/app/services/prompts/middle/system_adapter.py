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
            "delete": "del",
            "read": "type",
            "create_dir": "mkdir"
        },
        "Linux": {
            "list": "ls",
            "copy": "cp",
            "delete": "rm",
            "read": "cat",
            "create_dir": "mkdir"
        },
        "Darwin": {
            "list": "ls",
            "copy": "cp",
            "delete": "rm",
            "read": "cat",
            "create_dir": "mkdir"
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
    
    def generate_system_prompt(self) -> str:
        """
        生成系统信息Prompt - 嵌入到工具Prompt的开头
        
        Returns:
            格式化的系统信息字符串
        """
        system_name = self.get_system_name()
        path_format = self.get_path_format()
        commands = self.get_commands()
        
        prompt = f"""【当前系统】
{system_name}

【路径格式】
- Windows: C:\\Users\\xxx\\file.txt 或 C:/Users/xxx/file.txt
- Linux/Mac: /home/xxx/file.txt 或 /Users/xxx/file.txt

【命令格式】
- list: {commands.get('list', 'ls')}
- copy: {commands.get('copy', 'cp')}
- delete: {commands.get('delete', 'rm')}
- read: {commands.get('read', 'cat')}
- create_dir: {commands.get('create_dir', 'mkdir')}"""
        
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


def get_system_prompt() -> str:
    """快捷函数：获取系统Prompt字符串"""
    adapter = get_system_adapter()
    logger.info(f"[Prompt中间层] get_system_prompt() 被调用, 服务器OS: {adapter.get_system_name()}")
    return adapter.generate_system_prompt()


if __name__ == "__main__":
    # 测试
    adapter = SystemAdapter()
    print(f"当前系统: {adapter.get_system_name()}")
    print(f"路径格式: {adapter.get_path_format()}")
    print(f"命令: {adapter.get_commands()}")
    print("\n生成的Prompt:")
    print(adapter.generate_system_prompt())