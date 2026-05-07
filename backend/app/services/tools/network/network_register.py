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
    "http_request": """发送 HTTP 请求到指定的 URL，支持 GET、POST、PUT、DELETE、PATCH 等方法。

使用场景：
- 当用户需要调用 REST API 时使用
- 当用户想要发送 HTTP 请求获取数据或提交数据时使用
- 当用户需要进行网络请求时使用

参数说明：
- url：请求的目标 URL，必须是完全有效的 URL（如 https://api.example.com/data）
- method：HTTP 方法。可选值：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS
- headers：请求头对象（可选），如 {"Content-Type": "application/json", "Authorization": "Bearer token"}
- params：查询参数对象（可选），自动拼接到 URL
- body：请求体（可选），用于 POST、PUT、PATCH 方法，格式为字符串
- json_body：JSON请求体（可选），自动序列化为JSON并设置 Content-Type
- timeout：超时毫秒数，默认30000（30秒）
- verify_ssl：是否验证SSL证书（可选），默认True
- proxy：代理地址（可选），如需代理可传入
- retry：重试次数（可选），默认3次
- follow_redirects：是否跟随重定向（可选），默认True

【重要】返回响应的状态码、响应头和响应体

使用示例：
- GET请求：{"url": "https://api.example.com/users", "method": "GET"}
- POST请求：{"url": "https://api.example.com/users", "method": "POST", "headers": {"Content-Type": "application/json"}, "json_body": {"name": "张三"}}
- 带重试：{"url": "https://api.example.com/users", "retry": 5}""",
    "download_file": """从 URL 下载文件到本地，支持大文件流式下载、断点续传、进度显示。

使用场景：
- 当用户需要下载文件时使用
- 当用户想要下载图片、视频、安装包等文件时使用
- 当用户需要指定保存路径时使用
- 当下载中断后需要续传时使用（自动检测已下载部分）

参数说明：
- url：要下载文件的 URL（必填）
- destination_path：文件保存的完整路径（必填）
- headers：请求头字典（可选），如需要认证可传入
- timeout：下载超时时间（秒），默认 300，最大 3600
- chunk_size：下载分块大小（字节），默认 8192
- resume：是否启用断点续传（可选），默认 true，文件存在时自动尝试续传

【重要】返回下载结果，包含文件路径、下载大小、是否断点续传、进度百分比

使用示例：
- 简单下载：{"url": "https://example.com/file.zip", "destination_path": "D:/Downloads/file.zip"}
- 带认证下载：{"url": "https://private.com/file.zip", "destination_path": "D:/Downloads/file.zip", "headers": {"Authorization": "Bearer token"}}
- 禁止续传：{"url": "https://example.com/file.zip", "destination_path": "D:/Downloads/file.zip", "resume": false}""",
    "fetch_webpage": """获取和处理网页内容，支持多种格式提取和智能内容提取。

使用场景：
- 当用户需要获取网页内容时使用
- 当用户想要从网页中提取特定信息时使用
- 当用户需要将网页转为Markdown格式时使用

参数说明：
- url：完全有效的 URL
- prompt：内容提取提示（可选）。指定需要从网页中提取的信息，如"提取页面标题和主要内容"
- extract_format：提取格式（可选），可选值 markdown/html/text，默认 markdown
- js_render：是否启用JS渲染（可选），默认false
- timeout：超时毫秒数（可选），默认 30000
- max_tokens：最大返回字符数（可选），默认 8000
- user_agent：自定义 UA（可选），默认自动生成浏览器UA
- proxy：代理地址（可选）

【重要】返回网页的文本内容和提取格式

使用示例：
- 获取网页：{"url": "https://example.com", "prompt": "提取页面标题和主要内容"}
- JS渲染：{"url": "https://example.com", "js_render": true}""",
    "search_web": """搜索网络获取最新信息（使用DuckDuckGo API）。

使用场景：
- 当用户需要搜索网络获取最新信息时使用
- 当用户想要查询实时数据或新闻时使用
- 当用户需要获取网上最新的技术文档时使用

参数说明：
- query：搜索查询字符串（必填）
- num_results：结果数量（可选），默认 10
- allowed_domains：包含的域名（可选）
- blocked_domains：排除的域名（可选）
- time_range：时间范围（可选），可选值 any/d/w/m/y
- language：搜索语言（可选）
- safe_search：安全搜索级别（可选），可选值 strict/moderate/off
- proxy：代理地址（可选）

【重要】返回搜索结果列表，包含标题、URL 和摘要

使用示例：
- 简单搜索：{"query": "OpenAI function calling"}
- 限定域名：{"query": "React 19 新特性", "allowed_domains": ["github.com", "react.dev"]}
- 时间范围：{"query": "AI news", "time_range": "d"}""",
    "ping": """执行ping测试检查主机可达性，返回延迟、丢包率、TTL等网络诊断信息。

使用场景：
- 当用户需要检查网络连通性时使用
- 当用户想要测试服务器响应时间时使用
- 当用户需要诊断网络问题时使用

参数说明：
- host：目标主机地址（域名或IP）
- count：发送ping包数量，默认4
- timeout：每次ping的超时时间（秒），默认5

【重要】返回详细的ping测试结果，包括丢包率、延迟统计（最小/平均/最大）

使用示例：
- 测试连接：{"host": "google.com"}
- 指定包数：{"host": "google.com", "count": 6}""",
    "port_check": """检查目标主机的指定端口是否开放，支持socket连接测试。

使用场景：
- 当用户需要检查端口是否开放时使用
- 当用户需要测试服务状态时使用
- 当用户需要进行的端口扫描时使用

参数说明：
- host：目标主机地址（域名或IP）
- port：端口号（1-65535）
- timeout：连接超时时间（秒），默认3

【重要】返回端口是否开放以及服务识别结果

使用示例：
- 检查80端口：{"host": "google.com", "port": 80}
- 检查多个端口需要多次调用""",
}

# 工具名到实现函数的映射
NETWORK_TOOL_IMPLEMENTATIONS = {
    "http_request": http_request,
    "download_file": download_file,
    "fetch_webpage": fetch_webpage,
    "search_web": search_web,
    "ping": ping,
    "port_check": port_check,
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

# ============================================================
# 注册网络工具（按架构规范）
# ============================================================
def register_network_tools():
    """注册所有网络工具"""
    for tool_name in NETWORK_TOOL_DESCRIPTIONS:
        tool_registry.register(
            name=tool_name,
            description=NETWORK_TOOL_DESCRIPTIONS[tool_name],
            implementation=NETWORK_TOOL_IMPLEMENTATIONS[tool_name],
            input_model=NETWORK_TOOL_INPUT_MODELS[tool_name],
            category=ToolCategory.NETWORK,
            examples=NETWORK_TOOL_EXAMPLES.get(tool_name, []),
        )
    logger.info(f"已注册 {len(NETWORK_TOOL_DESCRIPTIONS)} 个网络工具")

# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    register_network_tools()
    _initialized = True
