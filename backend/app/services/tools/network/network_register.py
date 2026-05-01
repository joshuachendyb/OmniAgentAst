# -*- coding: utf-8 -*-
"""
Network Register - 网络通信工具注册点

【架构规范】2026-04-29 小沈
- network_register.py 作为网络工具的注册点
- 使用 registry.py 的 tool_registry.register() 显式注册
- 使用 Pydantic 模型注册，自动生成 OpenAI Schema

【工具列表】（共4个）
1. http_request - 发起HTTP请求
2. download_file - 下载文件到本地
3. fetch_webpage - 获取和处理网页内容
4. search_web - 搜索网络获取最新信息

【注册说明】
- 导入 network_register 时自动触发注册
- 按规范使用 input_model 参数

创建时间: 2026-04-29
更新时间: 2026-05-02
"""

# ============================================================
# 网络工具注册 - 使用 Pydantic 模型（按文档设计）
# ============================================================
import logging
from typing import Optional
from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

# 导入 Pydantic 模型
from app.services.tools.network.network_schema import (
    HttpRequestInput,
    DownloadFileInput,
    FetchWebpageInput,
    SearchWebInput,
)

# 导入工具函数
from app.services.tools.network.network_tools import (
    http_request,
    download_file,
    fetch_webpage,
    search_web,
)

# 工具描述
NETWORK_TOOL_DESCRIPTIONS = {
    "http_request": "发起HTTP请求，支持GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS方法，支持自定义请求头、查询参数和请求体",
    "download_file": "从URL下载文件到本地，支持大文件流式下载和断点续传",
    "fetch_webpage": "获取和处理网页内容，支持多种输出格式（markdown/html/text）和AI提取指令",
    "search_web": "搜索网络获取最新信息，支持域名过滤、时间范围、安全搜索等参数",
}

# 工具名到 Pydantic 模型的映射
NETWORK_TOOL_INPUT_MODELS = {
    "http_request": HttpRequestInput,
    "download_file": DownloadFileInput,
    "fetch_webpage": FetchWebpageInput,
    "search_web": SearchWebInput,
}

# 使用示例
NETWORK_TOOL_EXAMPLES = {
    "http_request": [
        {"url": "https://api.github.com/repos/python/cpython", "method": "GET", "timeout": 10},
        {"url": "https://httpbin.org/post", "method": "POST", "json_body": {"name": "test", "value": 123}, "timeout": 30},
    ],
    "download_file": [
        {"url": "https://github.com/python/cpython/archive/refs/heads/main.zip", "destination_path": "D:/Downloads/cpython-main.zip", "timeout": 300},
    ],
    "fetch_webpage": [
        {"url": "https://example.com", "extract_format": "markdown"},
        {"url": "https://docs.python.org/3/library/asyncio.html", "prompt": "提取asyncio的主要功能和使用示例"},
    ],
    "search_web": [
        {"query": "OpenAI function calling", "num_results": 10},
        {"query": "React 19 新特性", "allowed_domains": ["github.com", "react.dev"], "num_results": 5},
    ],
}


def _register_network_tools():
    """按文档5.1设计注册所有网络工具"""
    tool_methods = {
        "http_request": http_request,
        "download_file": download_file,
        "fetch_webpage": fetch_webpage,
        "search_web": search_web,
    }

    for name, method in tool_methods.items():
        desc = NETWORK_TOOL_DESCRIPTIONS.get(name, "")
        input_model = NETWORK_TOOL_INPUT_MODELS.get(name)
        examples = NETWORK_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.NETWORK,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[network_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 触发注册
_register_network_tools()
