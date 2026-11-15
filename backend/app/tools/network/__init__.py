# -*- coding: utf-8 -*-
"""
Network 模块 - 网络通信工具
"""
# 2026-08-14 - 小欧 - 改名名实相符: network_diagnose.py → ping_port.py(同步import)
# 2026-11-15 小欧 - 星号导入改显式导入: 星号导入下注册入口名来源不可静态判定, 显式导入后来源唯一, 工具注册行为不变

from app.tools.network.download_file import download
from app.tools.network.fetch_webpage import fetchpage
from app.tools.network.http_request import httpget
from app.tools.network.network_register import _register_network_tools
from app.tools.network.ping_port import ping_port
from app.tools.network.search_web import searchweb

__all__ = [
    "_register_network_tools",
    "httpget",
    "download",
    "fetchpage",
    "searchweb",
    "ping_port",
]
