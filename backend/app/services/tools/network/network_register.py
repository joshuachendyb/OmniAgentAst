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


【重要】返回响应的状态码、响应头和响应体

使用示例：
- GET请求：{"url": "https://api.example.com/users", "method": "GET"}
- POST请求：{"url": "https://api.example.com/users", "method": "POST", "headers": {"Content-Type": "application/json"}, "json_body": {"name": "张三"}}
- 带重试：{"url": "https://api.example.com/users", "retry": 5}

返回数据说明：
- code: 状态码，SUCCESS或ERR_NETWORK_INVALID_PARAM/ERR_NETWORK_INVALID_URL/ERR_NETWORK_HTTP_ERROR/ERR_NETWORK_TIMEOUT/ERR_NETWORK_REQUEST_ERROR/ERR_NETWORK_UNKNOWN
- data: 成功时为对象，失败时为None；成功时包含 status_code(HTTP状态码)、headers(响应头字典)、body(响应体，JSON自动解析为对象，否则为文本字符串)；HTTP错误时包含 status_code和body
- message: 结果描述信息""",
    "download_file": """从 URL 下载文件到本地，支持大文件流式下载、断点续传、进度显示。

使用场景：
- 当用户需要下载文件时使用
- 当用户想要下载图片、视频、安装包等文件时使用
- 当用户需要指定保存路径时使用
- 当下载中断后需要续传时使用（自动检测已下载部分）


【重要】返回下载结果，包含文件路径、下载大小、是否断点续传、进度百分比

使用示例：
- 简单下载：{"url": "https://example.com/file.zip", "destination_path": "D:/Downloads/file.zip"}
- 带认证下载：{"url": "https://private.com/file.zip", "destination_path": "D:/Downloads/file.zip", "headers": {"Authorization": "Bearer token"}}
- 禁止续传：{"url": "https://example.com/file.zip", "destination_path": "D:/Downloads/file.zip", "resume": false}

返回数据说明：
- code: 状态码，SUCCESS或ERR_NETWORK_INVALID_URL/ERR_NETWORK_INVALID_PATH/ERR_NETWORK_CREATE_DIR/ERR_NETWORK_WRITE_FILE/ERR_NETWORK_TIMEOUT/ERR_NETWORK_HTTP_ERROR/ERR_NETWORK_REQUEST_ERROR/ERR_NETWORK_UNKNOWN
- data: 成功时为对象，失败时为None；成功时包含 file_path(文件绝对路径)、file_size(本次下载字节数)、total_size(文件总字节数)、progress_percent(进度百分比0-100)、content_type(内容类型)
- message: 结果描述信息""",
    "fetch_webpage": """获取和处理网页内容，支持多种格式提取和智能内容提取。

使用场景：
- 当用户需要获取网页内容时使用
- 当用户想要从网页中提取特定信息时使用
- 当用户需要将网页转为Markdown格式时使用


【重要】返回网页的文本内容和提取格式

使用示例：
- 获取网页：{"url": "https://example.com", "prompt": "提取页面标题和主要内容"}
- JS渲染：{"url": "https://example.com", "js_render": true}

返回数据说明：
- code: 状态码，SUCCESS或ERR_NETWORK_INVALID_URL/ERR_NETWORK_JS_RENDER/ERR_NETWORK_TIMEOUT/ERR_NETWORK_HTTP_ERROR/ERR_NETWORK_REQUEST_ERROR/ERR_NETWORK_UNKNOWN
- data: 成功时为对象，失败时为None；成功时包含 url(请求地址)、content(提取的网页内容文本)、format(提取格式markdown/html/text)、content_type(响应内容类型)、status_code(HTTP状态码)、truncated(是否因max_tokens截断)；有prompt时额外包含 prompt(AI提取指令)和note(提示需LLM后处理)
- message: 结果描述信息""",
    "search_web": """搜索网络获取最新信息（使用DuckDuckGo API）。

使用场景：
- 当用户需要搜索网络获取最新信息时使用
- 当用户想要查询实时数据或新闻时使用
- 当用户需要获取网上最新的技术文档时使用


【重要】返回搜索结果列表，包含标题、URL 和摘要

使用示例：
- 简单搜索：{"query": "OpenAI function calling"}
- 限定域名：{"query": "React 19 新特性", "allowed_domains": ["github.com", "react.dev"]}
- 时间范围：{"query": "AI news", "time_range": "d"}

返回数据说明：
- code: 状态码，SUCCESS或ERR_SEARCH_QUERY_TOO_SHORT/ERR_NETWORK_UNKNOWN
- data: 成功时为对象，失败时为None；成功时包含 query(搜索关键词)、results(搜索结果列表，每项含title标题/url链接/snippet摘要/source来源引擎)、total(结果总数)、engine(使用的搜索引擎DuckDuckGo或Bing)、time_range(时间范围)、language(语言)
- message: 结果描述信息""",
    "ping": """执行ping测试检查主机可达性，返回延迟、丢包率、TTL等网络诊断信息。

使用场景：
- 当用户需要检查网络连通性时使用
- 当用户想要测试服务器响应时间时使用
- 当用户需要诊断网络问题时使用


【重要】返回详细的ping测试结果，包括丢包率、延迟统计（最小/平均/最大）

使用示例：
- 测试连接：{"host": "google.com"}
- 指定包数：{"host": "google.com", "count": 6}

返回数据说明：
- code: 状态码，SUCCESS或ERR_NETWORK_INVALID_HOST/ERR_NETWORK_TIMEOUT/ERR_NETWORK_COMMAND_NOT_FOUND/ERR_NETWORK_UNKNOWN
- data: 成功时为对象，失败时为None；成功时包含 host(目标主机)、packets_sent(发送包数)、packets_received(接收包数)、packets_lost(丢失包数)、loss_rate(丢包率百分比)、min_latency(最小延迟ms)、avg_latency(平均延迟ms)、max_latency(最大延迟ms)、is_reachable(是否可达布尔值)、raw_output(ping命令原始输出)
- message: 结果描述信息""",
    "port_check": """检查目标主机的指定端口是否开放，支持socket连接测试。

使用场景：
- 当用户需要检查端口是否开放时使用
- 当用户需要测试服务状态时使用
- 当用户需要进行的端口扫描时使用


【重要】返回端口是否开放以及服务识别结果

使用示例：
- 检查80端口：{"host": "google.com", "port": 80}
- 检查多个端口需要多次调用

返回数据说明：
- code: 状态码，SUCCESS或ERR_NETWORK_INVALID_HOST/ERR_NETWORK_INVALID_PORT/ERR_NETWORK_DNS_ERROR/ERR_NETWORK_CONNECTION_ERROR/ERR_NETWORK_UNKNOWN
- data: 成功时为对象，失败时为None；成功时包含 host(目标主机)、port(端口号)、is_open(是否开放布尔值)、service(服务名称，已知端口返回如SSH/HTTP/HTTPS等，未知返回Unknown)；DNS错误或连接错误时is_open为False、service为None
- message: 结果描述信息""",
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
        input_model = NETWORK_TOOL_INPUT_MODELS[tool_name]
        examples = NETWORK_TOOL_EXAMPLES.get(tool_name, [])
        tool_registry.register(
            name=tool_name,
            description=NETWORK_TOOL_DESCRIPTIONS[tool_name],
            implementation=NETWORK_TOOL_IMPLEMENTATIONS[tool_name],
            input_model=input_model,
            category=ToolCategory.NETWORK,
            examples=examples,
        )
        logger.info(
            f"[network_register] 已注册工具: {tool_name}, 使用 Pydantic 模型: {input_model.__name__}, examples: {len(examples)}个"
        )

# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    register_network_tools()
    _initialized = True
