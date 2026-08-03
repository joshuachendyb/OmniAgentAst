# -*- coding: utf-8 -*-
"""
Network Register - 网络通信工具注册点

【架构规范】2026-04-29 小沈
- network_register.py 作为网络工具的注册点
- 使用 registry.py 的 tool_registry.register() 显式注册
- 使用 Pydantic 模型注册,自动生成 OpenAI Schema

【工具列表】(共5个)— 【2026-05-17 小沈】P1: 6→5,ping+port_check→network_diagnose
【2026-07-20 小欧】加描述规范:工具描述保持简洁不冗余,能力详情与默认支持能力只写在 schema 类 docstring,禁止在 register 工具描述里重复
1. httpget - 发起HTTP请求
2. download - 下载文件到本地
3. fetchpage - 获取和处理网页内容
4. searchweb - 搜索网络获取最新信息
5. ping_port - 网络连通性诊断(ping+端口检测,原名network_diagnose)

创建时间: 2026-04-29
更新时间: 2026-05-17 小沈
"""

# ============================================================
# 网络工具注册 - 使用 Pydantic 模型(按文档设计)
# ============================================================
from app.tools.registry import register_tool, tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger
import socket
import time
from typing import Any, Dict, Optional

# 网络工具依赖配置 — 小健 2026-06-18
# 每个工具对应的第三方依赖包列表
# 注意：httpx必须使用0.26.0版本，httpcore必须使用1.0.1版本（AGENTS.md明确要求）
NETWORK_TOOL_DEPENDENCIES = {
    "httpget": ["httpx==0.26.0", "httpcore==1.0.1"],
    "download": ["httpx==0.26.0", "httpcore==1.0.1"],
    "fetchpage": ["httpx==0.26.0", "httpcore==1.0.1"],
    "searchweb": ["httpx==0.26.0", "httpcore==1.0.1"],
    "ping_port": [],  # 使用内置库
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

def check_network() -> Dict[str, Any]:
    """检查网络连通性 — 小欧 2026-06-24 从3个文件中提取公共函数"""
    test_hosts = [("dns.google", 53), ("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in test_hosts:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            t1 = time.time()
            sock.connect((host, port))
            latency = (time.time() - t1) * 1000
            return {"connected": True, "host": host, "latency_ms": round(latency, 2)}
        except (socket.timeout, socket.error, OSError):
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
    return {"connected": False}


# 导入 Pydantic 模型
from app.tools.network.network_schema import (
    HttpRequestInput,
    DownloadFileInput,
    FetchWebpageInput,
    SearchWebInput,
    NetworkDiagnoseInput,
)

from app.tools.network.http_request import httpget
from app.tools.network.download_file import download
from app.tools.network.fetch_webpage import fetchpage
from app.tools.network.search_web import searchweb
from app.tools.network.network_diagnose import ping_port

# 工具描述
# 【描述规范】2026-07-20 北京老陈 — 工具描述(本 NETWORK_TOOL_DESCRIPTIONS 字典)保持简洁、不冗余:
# 能力详情与默认支持的能力只写在对应 Schema 类的 docstring 里(会进入 JSON Schema 发给 LLM);
# 本字典仅作一句话路由/适用场景说明,严禁重复 schema docstring 内容。
NETWORK_TOOL_DESCRIPTIONS = {
    "httpget": """发送HTTP请求到指定URL,支持GET/POST/PUT/DELETE等方法。适用场景:需要调用REST API获取数据、提交数据、调用Web服务时使用。""",
    "download": """从URL下载文件到本地磁盘。适用场景:需要下载图片、安装包、数据文件等到本地时使用。""",
    "fetchpage": """获取网页内容并提取正文,支持Markdown/HTML格式输出。适用场景:需要阅读网页文档、从网页提取信息时使用。""",
    "searchweb": """使用搜索引擎查询最新信息。适用场景:需要获取实时新闻、技术文档、问题解决方案时使用。""",
    "ping_port": """检测网络连通性,支持ping和TCP端口检测。适用场景:需要排查网络连接问题时使用。""",
}

# 工具名到实现函数的映射
NETWORK_TOOL_IMPLEMENTATIONS = {
    "httpget": httpget,
    "download": download,
    "fetchpage": fetchpage,
    "searchweb": searchweb,
    "ping_port": ping_port,
}

# 工具名到 Pydantic 模型的映射
NETWORK_TOOL_INPUT_MODELS = {
    "httpget": HttpRequestInput,
    "download": DownloadFileInput,
    "fetchpage": FetchWebpageInput,
    "searchweb": SearchWebInput,
    "ping_port": NetworkDiagnoseInput,
}

# 使用示例
NETWORK_TOOL_EXAMPLES = {
    "httpget": [
        {"url": "https://api.github.com/repos/python/cpython", "method": "GET"},
        {"url": "https://httpbin.org/post", "method": "POST", "body": {"name": "test", "value": 123}},
    ],
    "download": [
        {"url": "https://github.com/python/cpython/archive/refs/heads/main.zip", "destination_path": "D:/Downloads/cpython-main.zip"},
    ],
    "fetchpage": [
        {"url": "https://example.com", "extract_format": "markdown"},
        {"url": "https://docs.python.org/3/library/asyncio.html", "prompt": "提取asyncio的主要功能和使用示例"},
    ],
    "searchweb": [
        {"query": "OpenAI function calling"},
        {"query": "React 19 新特性"},
    ],
    "ping_port": [
        {"host": "8.8.8.8"},
        {"host": "8.8.8.8", "mode": "port", "port": 53},
        {"host": "baidu.com"},
        {"host": "127.0.0.1", "mode": "port", "port": 8000},
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
        failure_hint_fn = _http_request_failure_hint if tool_name == "httpget" else None
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
