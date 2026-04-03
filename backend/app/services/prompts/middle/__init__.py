"""
Prompt中间层 - 系统信息适配器

导出接口：
- SystemAdapter: 系统信息适配器类
- get_system_adapter(): 获取适配器实例
- get_system_prompt(): 快捷函数，获取系统Prompt字符串

创建时间: 2026-03-24 17:25:00
作者: 小沈
"""
from app.services.prompts.middle.system_adapter import (
    SystemAdapter,
    get_system_adapter,
    get_system_prompt
)

__all__ = [
    "SystemAdapter",
    "get_system_adapter", 
    "get_system_prompt"
]