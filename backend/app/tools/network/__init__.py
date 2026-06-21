# -*- coding: utf-8 -*-
"""
Network 模块 - 网络通信工具
"""

from app.tools.network.network_register import *
from app.tools.network.http_request import http_request
from app.tools.network.download_file import download_file
from app.tools.network.fetch_webpage import fetch_webpage
from app.tools.network.search_web import search_web
from app.tools.network.network_diagnose import network_diagnose

__all__ = [
    "http_request",
    "download_file",
    "fetch_webpage",
    "search_web",
    "network_diagnose",
]
