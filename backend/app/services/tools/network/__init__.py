# -*- coding: utf-8 -*-
"""
Network 模块 - 网络通信工具

【架构规范】2026-04-29 小沈
- network_register.py: 工具注册点（导入触发注册）
- network_tools.py: 具体实现
- network_schema.py: Pydantic 模型

目录结构：
    network/
    ├── __init__.py           # 本文件，导入 network_register 触发注册
    ├── network_register.py   # 工具注册点
    ├── network_tools.py      # 具体实现
    └── network_schema.py     # Pydantic 模型

创建时间: 2026-04-29
"""

# 导入 network_register 触发注册
from app.services.tools.network import network_register
from app.services.tools.network import network_tools

from app.services.tools.network.network_tools import (
    http_request,
    download_file,
    fetch_webpage,
    search_web,
    ping,
    port_check,
)

__all__ = [
    "http_request",
    "download_file",
    "fetch_webpage",
    "search_web",
    "ping",
    "port_check",
]
