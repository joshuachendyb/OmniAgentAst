# -*- coding: utf-8 -*-
"""
Network Register - 网络通信工具注册点

【架构规范】2026-04-29 小沈
- network_register.py 作为网络工具的注册点
- 使用 registry.py 的 tool_registry.register() 显式注册
- 使用 Pydantic 模型注册，自动生成 OpenAI Schema

【工具列表】（共6个）
1. http_request - 发起HTTP请求
2. download_file - 下载文件到本地
3. fetch_webpage - 获取和处理网页内容
4. search_web - 搜索网络获取最新信息
5. ping - 执行ping测试（小沈 2026-05-02）
6. port_check - 检查端口是否开放（小沈 2026-05-02）

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
    PingInput,
    PortCheckInput,
)

# 导入工具函数
from app.services.tools.network.network_tools import (
    http_request,
    download_file,
    fetch_webpage,
    search_web,
    ping,
    port_check,
)

# 工具描述
NETWORK_TOOL_DESCRIPTIONS = {
    "http_request": """发送 HTTP 请求到指定的 URL，支持 GET、POST、PUT、DELETE、PATCH 等方法。\n\n使用场景：\n- 当用户需要调用 REST API 时使用\n- 当用户想要发送 HTTP 请求获取数据或提交数据时使用\n- 当用户需要进行网络请求时使用\n\n参数说明：\n- url：请求的目标 URL，必须是完全有效的 URL（如 https://api.example.com/data）\n- method：HTTP 方法。可选值：GET、POST、PUT、DELETE、PATCH\n- headers：请求头对象（可选），如 {\"Content-Type\": \"application/json\", \"Authorization\": \"Bearer token\"}\n- body：请求体（可选），用于 POST、PUT、PATCH 方法，格式为字符串\n- timeout：超时毫秒数，默认30000（30秒）\n\n【重要】返回响应的状态码、响应头和响应体\n\n使用示例：\n- GET请求：{\"url\": \"https://api.example.com/users\", \"method\": \"GET\"}\n- POST请求：{\"url\": \"https://api.example.com/users\", \"method\": \"POST\", \"headers\": {\"Content-Type\": \"application/json\"}, \"body\": \"{\\\"name\\\": \\\"张三\\\"}\"""",
    "download_file": """从 URL 下载文件到本地，支持大文件流式下载。\n\n使用场景：\n- 当用户需要下载文件时使用\n- 当用户想要下载图片、视频、安装包等文件时使用\n- 当用户需要指定保存路径时使用\n\n参数说明：\n- url：要下载文件的 URL（必填）\n- destination_path：文件保存的完整路径（必填）\n- headers：请求头字典（可选），如需要认证可传入\n- timeout：下载超时时间（秒），默认 300，最大 3600\n- chunk_size：下载分块大小（字节），默认 8192\n\n【重要】返回下载结果，包含文件路径和大小\n\n使用示例：\n- 简单下载：{\"url\": \"https://example.com/file.zip\", \"destination_path\": \"D:/Downloads/file.zip\"}\n- 带认证下载：{\"url\": \"https://private.com/file.zip\", \"destination_path\": \"D:/Downloads/file.zip\", \"headers\": {\"Authorization\": \"Bearer token\"}}""",
    "fetch_webpage": """获取和处理网页内容，带 AI 分析功能。\n\n使用场景：\n- 当用户需要获取网页内容时使用\n- 当用户想要从网页中提取特定信息时使用\n- 当用户需要分析网页内容时使用\n\n参数说明：\n- url：完全有效的 URL\n- prompt：提取指令（可选），默认提取核心内容和摘要\n- extract_format：提取格式（可选），默认 markdown\n- js_render：是否启用 JS 渲染（可选），默认 false\n- timeout：超时毫秒数（可选），默认 30000\n- max_tokens：最大返回 Token 数（可选），默认 8000\n- user_agent：自定义 UA（可选），Agent 自动注入随机浏览器 UA\n- proxy：代理地址（可选），Agent 优先直连，失败后自动使用代理重试\n\n【重要】返回网页的文本内容和 AI 分析结果\n\n使用示例：\n- 获取网页：{\"url\": \"https://example.com\", \"prompt\": \"提取页面标题和主要内容\"}""",
    "search_web": """搜索网络获取最新信息。\n\n使用场景：\n- 当用户需要搜索网络获取最新信息时使用\n- 当用户想要查询实时数据或新闻时使用\n- 当用户需要获取网上最新的技术文档时使用\n\n参数说明：\n- query：搜索查询字符串\n- allowed_domains：包含的域名数组（可选）\n- blocked_domains：排除的域名数组（可选）\n- num_results：结果数量（可选），默认 10\n- time_range：时间范围（可选），可选值 any/d/w/m/y\n- language：搜索语言（可选），默认匹配当前会话语言\n- safe_search：安全搜索级别（可选），可选值 strict/moderate/off\n- proxy：代理地址（可选），Agent 优先直连，失败后自动使用代理重试\n\n【重要】返回搜索结果列表，包含标题、URL 和摘要\n\n使用示例：\n- 简单搜索：{\"query\": \"OpenAI function calling\"}\n- 限定域名搜索：{\"query\": \"React 19 新特性\", \"allowed_domains\": [\"github.com\", \"react.dev\"]}""",
    "ping": """执行ping测试检查主机可达性，返回延迟、丢包率、TTL等网络诊断信息。\n\n使用场景：\n- 当用户需要检查网络连通性时使用\n- 当用户想要测试服务器响应时间时使用\n- 当用户需要诊断网络问题时使用\n\n参数说明：\n- host：目标主机地址（域名或IP）\n- count：发送ping包数量，默认4\n- timeout：每次ping的超时时间（秒），默认5\n\n【重要】返回详细的ping测试结果，包括丢包率、延迟统计（最小/平均/最大）\n\n使用示例：\n- 测试连接：{\"host\": \"google.com\"}\n- 指定包数：{\"host\": \"google.com\", \"count\": 6}""",
    "port_check": """检查目标主机的指定端口是否开放，支持socket连接测试。\n\n使用场景：\n- 当用户需要检查端口是否开放时使用\n- 当用户需要测试服务状态时使用\n- 当用户需要进行端口扫描时使用\n\n参数说明：\n- host：目标主机地址（域名或IP）\n- port：端口号（1-65535）\n- timeout：连接超时时间（秒），默认3\n\n【重要】返回端口是否开放以及服务识别结果\n\n使用示例：\n- 检查80端口：{\"host\": \"google.com\", \"port\": 80}\n- 检查多个端口需要多次调用""",
}

# 工具名到 Pydantic 模型的映射
NETWORK_TOOL_INPUT_MODELS = {
    "http_request": HttpRequestInput,
    "download_file": DownloadFileInput,
    "fetch_webpage": FetchWebpageInput,
    "search_web": SearchWebInput,
    "ping": PingInput,
    "port_check": PortCheckInput,
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
    "ping": [
        {"host": "8.8.8.8", "count": 4, "timeout": 5},
        {"host": "www.baidu.com", "count": 4},
    ],
    "port_check": [
        {"host": "127.0.0.1", "port": 8080, "timeout": 3},
        {"host": "www.example.com", "port": 443},
    ],
}


def _register_network_tools():
    """按文档5.1设计注册所有网络工具"""
    tool_methods = {
        "http_request": http_request,
        "download_file": download_file,
        "fetch_webpage": fetch_webpage,
        "search_web": search_web,
        "ping": ping,
        "port_check": port_check,
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
