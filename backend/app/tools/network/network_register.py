# -*- coding: utf-8 -*-
"""
Network Register - 网络通信工具注册点

【架构规范】2026-04-29 小沈
- network_register.py 作为网络工具的注册点
- 使用 registry.py 的 tool_registry.register() 显式注册
- 使用 Pydantic 模型注册,自动生成 OpenAI Schema

【工具列表】(共5个)— 【2026-05-17 小沈】P1: 6→5,ping+port_check→network_diagnose
1. http_request - 发起HTTP请求
2. download_file - 下载文件到本地
3. fetch_webpage - 获取和处理网页内容
4. search_web - 搜索网络获取最新信息
5. network_diagnose - 网络连通性诊断(合并ping+port_check)

创建时间: 2026-04-29
更新时间: 2026-05-17 小沈
"""

# ============================================================
# 网络工具注册 - 使用 Pydantic 模型(按文档设计)
# ============================================================
from app.tools.registry import register_tool, tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger
from typing import Optional

# 网络工具依赖配置 — 小健 2026-06-18
# 每个工具对应的第三方依赖包列表
# 注意：httpx必须使用0.26.0版本，httpcore必须使用1.0.1版本（AGENTS.md明确要求）
NETWORK_TOOL_DEPENDENCIES = {
    "http_request": ["httpx==0.26.0", "httpcore==1.0.1"],
    "download_file": ["httpx==0.26.0", "httpcore==1.0.1"],
    "fetch_webpage": ["httpx==0.26.0", "httpcore==1.0.1"],
    "search_web": ["httpx==0.26.0", "httpcore==1.0.1"],
    "network_diagnose": [],  # 使用内置库
}


def _http_request_failure_hint(tool_params: Optional[dict] = None) -> str:
    """http_request失败时的国内替代URL提示 — 小健 2026-05-24"""
    failed_url = (tool_params or {}).get("url", "")
    hint = "⚠️ 网络请求失败。如果是访问国外服务超时,请换用国内可达的替代地址:\n"
    hint += "  - 查公网IP → 用 https://httpbin.org/ip 或 https://myip.ipip.net\n"
    hint += "  - 查IP详情 → 用 https://ipapi.co/json/ 或 https://ip.sb/api/\n"
    hint += "  - DNS查询 → 用 https://dns.alidns.com/resolve?name=域名&type=A\n"
    hint += "  - 网络连通 → 用 ping 测试国内域名(如 baidu.com)\n"
    if failed_url:
        hint += f"  失败URL: {failed_url}\n"
    hint += "请勿重复请求同一失败URL!"
    return hint

# 导入 Pydantic 模型
from app.tools.network.network_schema import (
    HttpRequestInput,
    DownloadFileInput,
    FetchWebpageInput,
    SearchWebInput,
    NetworkDiagnoseInput,
)

from app.tools.network.network_tools import (
    http_request,
    download_file,
    fetch_webpage,
    search_web,
    network_diagnose,
)

from app.tools.system.system_tools import net_connections
from app.tools.system.system_schema import NetConnectionsInput

# 工具描述
NETWORK_TOOL_DESCRIPTIONS = {
    "http_request": """发送HTTP请求到指定URL。支持GET/POST/PUT/DELETE/PATCH等方法,支持自定义请求头、JSON请求体、查询参数、超时设置和重试次数。返回响应的状态码、响应头和响应体(JSON自动解析为对象)。访问国外服务失败时提示可选的国内替代地址。适用场景:需要调用REST API获取数据、提交数据、调用Web服务接口时使用。""",
    "download_file": """从URL下载文件到本地,支持大文件流式下载。支持自定义请求头(如认证Token)、超时设置。自动创建目标目录。返回文件保存路径、下载字节数、文件总大小、进度百分比和内容类型。适用场景:需要下载网络上的图片、安装包、数据文件等到本地磁盘时使用。""",
    "fetch_webpage": """获取网页内容并提取正文,支持Markdown/HTML/Text格式输出。当需要从网页中提取特定信息时,可通过prompt参数指定提取指令(由LLM后处理)。支持JavaScript渲染(js_render=True)和超时设置。返回提取的网页内容、格式类型和HTTP状态码。适用场景:需要获取网页文档内容、从网页中提取特定数据、将网页转为Markdown后供LLM阅读时使用。""",
    "search_web": """使用搜索引擎查询最新信息,默认使用国内可用的Bing中国搜索。支持指定搜索结果数量、限定搜索域名范围。返回搜索结果列表(含标题、URL、摘要)、结果总数和使用的搜索引擎。num_results参数建议:概览类查询用5~8,深度调研类用15~20,默认10。适用场景:需要获取实时信息、新闻动态、技术文档、问题解决方案等最新网络信息时使用。""",
    "network_diagnose": """网络连通性诊断工具。支持ping测试和端口检测。适用场景:需要检测网络连通性、排查网络问题时使用。""",
    "net_connections": """获取当前系统的网络连接列表。支持按连接类型(TCP/UDP)、连接状态(ESTABLISHED/LISTEN等)和端口号过滤。可获取关联进程信息(进程名和PID)。最多返回200条连接记录。适用场景:需要排查端口占用问题、查看某个端口的连接状态、了解当前网络活动情况时使用。""",
}

# 工具名到实现函数的映射
NETWORK_TOOL_IMPLEMENTATIONS = {
    "http_request": http_request,
    "download_file": download_file,
    "fetch_webpage": fetch_webpage,
    "search_web": search_web,
    "network_diagnose": network_diagnose,
    "net_connections": net_connections,
}

# 工具名到 Pydantic 模型的映射
NETWORK_TOOL_INPUT_MODELS = {
    "http_request": HttpRequestInput,
    "download_file": DownloadFileInput,
    "fetch_webpage": FetchWebpageInput,
    "search_web": SearchWebInput,
    "network_diagnose": NetworkDiagnoseInput,
    "net_connections": NetConnectionsInput,
}

# 使用示例
NETWORK_TOOL_EXAMPLES = {
    "http_request": [
        {"url": "https://api.github.com/repos/python/cpython", "method": "GET", "timeout": 10000},
        {"url": "https://httpbin.org/post", "method": "POST", "json_body": {"name": "test", "value": 123}, "timeout": 30000},
    ],
    "download_file": [
        {"url": "https://github.com/python/cpython/archive/refs/heads/main.zip", "destination_path": "D:/Downloads/cpython-main.zip", "timeout": 300000},
    ],
    "fetch_webpage": [
        {"url": "https://example.com", "extract_format": "markdown"},
        {"url": "https://docs.python.org/3/library/asyncio.html", "prompt": "提取asyncio的主要功能和使用示例"},
    ],
    "search_web": [
        {"query": "OpenAI function calling", "num_results": 10},
        {"query": "React 19 新特性", "allowed_domains": ["github.com", "react.dev"], "num_results": 5},
    ],
    "network_diagnose": [
        {"host": "8.8.8.8"},
        {"host": "8.8.8.8", "mode": "port", "port": 53},
        {"host": "baidu.com", "count": 10},
        {"host": "127.0.0.1", "mode": "port", "port": 8000},
    ],
    "net_connections": [
        {},
        {"kind": "tcp", "state": "established"},
        {"filter_port": 8080, "process_info": True},
    ],
}

# ============================================================
# 注册网络工具(按架构规范)
# ============================================================
def _register_network_tools():
    """注册所有网络工具"""
    for tool_name in NETWORK_TOOL_DESCRIPTIONS:
        input_model = NETWORK_TOOL_INPUT_MODELS[tool_name]
        examples = NETWORK_TOOL_EXAMPLES.get(tool_name, [])
        failure_hint_fn = _http_request_failure_hint if tool_name == "http_request" else None
        tool_registry.register(
            name=tool_name,
            description=NETWORK_TOOL_DESCRIPTIONS[tool_name],
            implementation=NETWORK_TOOL_IMPLEMENTATIONS[tool_name],
            input_model=input_model,
            category=ToolCategory.NETWORK,
            examples=examples,
            failure_hint_fn=failure_hint_fn,
            dependencies=NETWORK_TOOL_DEPENDENCIES.get(tool_name, []),
        )
        logger.debug(
            f"[network_register] 已注册工具: {tool_name}, 使用 Pydantic 模型: {input_model.__name__}, examples: {len(examples)}个"
        )

# 【Phase 1修复 小健 2026-05-14】删除模块级注册代码,改为ensure_tools_registered统一调用
# 原代码:import时自动执行register_network_tools(),破坏按需注册
# 现在:导出register函数供ensure_tools_registered显式调用

__all__ = ["_register_network_tools"]
