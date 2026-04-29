# -*- coding: utf-8 -*-
"""
Network Register - 网络通信工具注册点

【架构规范】2026-04-29 小沈
- network_register.py 作为网络工具的注册点
- 使用 registry.py 的 tool_registry.register() 显式注册
- 使用 Pydantic 模型注册，自动生成 OpenAI Schema

【工具列表】（共2个）
1. http_request - 发起HTTP请求
2. download_file - 下载文件到本地

【注册说明】
- 导入 network_register 时自动触发注册
- 按规范使用 input_model 参数

创建时间: 2026-04-29
"""

# ============================================================
# 网络工具注册 - 使用 Pydantic 模型（按文档设计）
# ============================================================
import logging
from typing import Optional
from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

# 导入 Pydantic 模型
# 【小健 2026-04-29】强制规范：新增工具必须从network_schema导入对应Pydantic模型，禁止手动编写input_schema字典
from app.services.tools.network.network_schema import (
    HttpRequestInput,
    DownloadFileInput,
)

# 导入工具函数
from app.services.tools.network.network_tools import (
    http_request,
    download_file,
)

# 工具描述
NETWORK_TOOL_DESCRIPTIONS = {
    "http_request": "发起HTTP请求，支持GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS方法，支持自定义请求头、查询参数和请求体",
    "download_file": "从URL下载文件到本地，支持大文件流式下载和断点续传",
}

# 【小健 2026-04-29】强制映射：工具名与Pydantic模型一一对应
# 【2026-04-29 小沈新增】工具名到 Pydantic 模型的映射（按文档5.1设计）
NETWORK_TOOL_INPUT_MODELS = {
    "http_request": HttpRequestInput,
    "download_file": DownloadFileInput,
}

# 使用示例
NETWORK_TOOL_EXAMPLES = {
    "http_request": [
        {"url": "https://api.github.com/repos/python/cpython", "method": "GET", "timeout": 10},
        {"url": "https://httpbin.org/post", "method": "POST", "json_body": {"name": "test", "value": 123}, "timeout": 30},
        {"url": "https://api.example.com/search", "method": "GET", "params": {"q": "python", "page": 1}, "timeout": 15},
    ],
    "download_file": [
        {"url": "https://github.com/python/cpython/archive/refs/heads/main.zip", "destination_path": "D:/Downloads/cpython-main.zip", "timeout": 300},
        {"url": "https://example.com/file.pdf", "destination_path": "C:/Users/用户名/Documents/file.pdf", "timeout": 120},
    ],
}


def _register_network_tools():
    """按文档5.1设计注册所有网络工具"""
    # 统一的工具映射 - 注册名与实际函数名一致
    tool_methods = {
        "http_request": http_request,
        "download_file": download_file,
    }

    # 注册所有工具
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
