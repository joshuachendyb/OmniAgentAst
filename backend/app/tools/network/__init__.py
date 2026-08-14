# -*- coding: utf-8 -*-
"""
Network 模块 - 网络通信工具
"""
# 2026-08-14 - 小欧 - 改名名实相符: network_diagnose.py → ping_port.py(同步import)

from app.tools.network.network_register import *
from app.tools.network.http_request import httpget
from app.tools.network.download_file import download
from app.tools.network.fetch_webpage import fetchpage
from app.tools.network.search_web import searchweb
from app.tools.network.ping_port import ping_port

__all__ = [
    "httpget",
    "download",
    "fetchpage",
    "searchweb",
    "ping_port",
]
