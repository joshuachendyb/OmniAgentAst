# -*- coding: utf-8 -*-
"""
Network 模块 - 网络通信工具
"""

from app.tools.network.network_register import *
from app.tools.network.network_tools import (
    http_request,
    download_file,
    fetch_webpage,
    search_web,
    network_diagnose,
)

__all__ = [
    "http_request",
    "download_file",
    "fetch_webpage",
    "search_web",
    "network_diagnose",
]
