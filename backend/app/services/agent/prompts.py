"""兼容旧导入路径：app.services.agent.prompts。"""

from app.services.prompts.file.file_prompts import FileOperationPrompts

__all__ = ["FileOperationPrompts"]
