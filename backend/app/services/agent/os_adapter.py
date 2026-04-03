"""
操作系统适配器实现

【创建时间】2026-03-20 11:23:15 小强
【参考】Structured-Outputs-自适应兼容方案-小沈-2026-03-20.md 3.2.3节

功能：
1. OSAdapter 类 - 检测当前系统，生成系统提示信息
2. get_system_prompt() - 生成系统提示信息
3. get_tool_descriptions() - 生成工具描述中的系统适配说明
"""

import platform


class OSAdapter:
    """
    操作系统适配器
    
    检测当前系统，生成系统提示信息
    """
    
    def __init__(self):
        self.system = platform.system()  # Windows / Linux / Darwin
    
    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"
    
    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"
    
    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"
    
    @property
    def path_separator(self) -> str:
        """路径分隔符"""
        return "\\" if self.is_windows else "/"
    
    @property
    def commands(self) -> dict:
        """常用命令映射"""
        if self.is_windows:
            return {
                "list": "dir",
                "copy": "copy",
                "move": "move",
                "delete": "del",
                "read": "type",
                "write": "echo",
                "mkdir": "mkdir",
                "rmdir": "rmdir",
            }
        else:
            return {
                "list": "ls",
                "copy": "cp",
                "move": "mv",
                "delete": "rm",
                "read": "cat",
                "write": "echo",
                "mkdir": "mkdir",
                "rmdir": "rmdir",
            }
    
    def get_system_prompt(self) -> str:
        """生成系统提示信息"""
        return f"""【操作系统】
{self.system}

【路径格式】
- Windows: C:\\Users\\xxx\\file.txt
- Linux/Mac: /home/xxx/file.txt

【当前系统命令】
{chr(10).join(f"- {k}: {v}" for k, v in self.commands.items())}

重要：请返回适用于 {self.system} 系统的命令和路径格式。"""
    
    def get_tool_descriptions(self) -> dict:
        """生成工具描述中的系统适配说明"""
        path_example = "C:\\Users\\xxx\\file.txt" if self.is_windows else "/home/xxx/file.txt"
        return {
            "path": f"文件路径，格式如: {path_example}",
            "description": "Windows 使用 dir/copy/del/type，Linux/Mac 使用 ls/cp/rm/cat"
        }
    
    def __repr__(self) -> str:
        return f"OSAdapter(system={self.system})"


# 导出
__all__ = ["OSAdapter"]
