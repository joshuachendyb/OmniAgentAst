# -*- coding: utf-8 -*-
"""
网络辅助函数模块 - 网络相关的内部辅助函数

【创建时间】2026-05-17 小沈
【说明】从 support_tool/support_tool_tools.py 迁移 check_network_connectivity 和 validate_url 函数
       从 network/network_tools.py 迁移 _html_to_markdown 和 _decode_bing_redirect_url
       这些函数作为内部Helper，不注册到tool_registry，仅供Agent内部代码调用

包含函数（6个）：
- _check_network: 检查网络连通性（内部Helper）
- _validate_url: 验证URL格式（内部Helper）
- _html_to_markdown: 简易HTML转Markdown（内部Helper）- 小沈 2026-05-17
- _decode_bing_redirect_url: 解码Bing跳转URL（内部Helper）- 小沈 2026-05-17
- well_known_ports: 常用端口映射表（内部常量）- 小健 2026-05-18
- _create_http_client: 统一创建httpx.AsyncClient（内部Helper）- 小健 2026-05-18

Author: 小沈 - 2026-05-17
"""

import base64
import os
import re
import socket
import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.services.agent.tool_result_utils import create_tool_result


def _check_network() -> Dict[str, Any]:
    """检查网络连通性（内部Helper） - 小沈 2026-05-17（从 support_tool_tools.py 迁移）

    测试与公共DNS服务器的连通性，返回连通状态和延迟。

    Returns:
        Dict[str, Any]: {code, data, message}
        - data.connected: 网络是否连通(bool)
        - data.host: 连通的测试主机(str，连通时)
        - data.latency_ms: 延迟毫秒数(float，连通时)
    """
    test_hosts = [
        ("dns.google", 53),
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
    ]

    for host, port in test_hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            t1 = time.time()
            sock.connect((host, port))
            latency = (time.time() - t1) * 1000
            sock.close()
            return create_tool_result(data={"connected": True, "host": host, "latency_ms": round(latency, 2)}, message=f"网络连通，延迟: {latency:.1f}ms")
        except (socket.timeout, socket.error, OSError):
            continue

    return create_tool_result(data={"connected": False}, message="网络不可用")


def _validate_url(url: str) -> Dict[str, Any]:
    """验证URL格式（内部Helper） - 小沈 2026-05-17（从 support_tool_tools.py 迁移）

    检查URL是否包含有效的scheme和netloc，scheme是否在允许列表中。

    Args:
        url: 要验证的URL字符串

    Returns:
        Dict[str, Any]: {code, data, message}
        - data.valid: URL是否有效(bool)
        - data.scheme: 协议类型(str)
        - data.netloc: 网络位置(str)
        - data.path: 路径(str)
    """
    try:
        parsed = urlparse(url)
        is_valid = bool(parsed.scheme) and bool(parsed.netloc)
        valid_schemes = {"http", "https", "ftp", "ftps", "ws", "wss"}
        scheme_ok = parsed.scheme in valid_schemes

        return create_tool_result(
            data={
                "valid": is_valid and scheme_ok,
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "path": parsed.path,
            },
            message="URL格式有效" if (is_valid and scheme_ok) else "URL格式无效"
        )
    except Exception as e:
        return create_tool_result(data={"valid": False, "error": str(e)}, message=f"URL验证失败: {str(e)}")


__all__ = [
    "_check_network",
    "_validate_url",
    "_html_to_markdown",
    "_decode_bing_redirect_url",
    "well_known_ports",
    "_create_http_client",
]


def _html_to_markdown(html: str) -> str:
    """简易HTML转Markdown - 小沈 2026-05-17（从 network_tools.py 迁移）
    纯文本转换逻辑，不依赖网络模块状态；document分类HTML处理可复用。
    """
    text = html
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL|re.IGNORECASE)
    
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1\n', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.IGNORECASE)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.IGNORECASE)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.IGNORECASE)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()


def _decode_bing_redirect_url(url: str) -> str:
    """解码Bing ck/a跳转链接，提取真实URL - 小沈 2026-05-17（从 network_tools.py 迁移）
    Bing使用 https://www.bing.com/ck/a?!&&p=<hash>&u=<base64_url> 格式的跳转链接
    纯URL解码逻辑，独立可复用。
    """
    if "bing.com/ck/a" not in url:
        return url
    u_match = re.search(r'[?&]u=([^&]+)', url)
    if u_match:
        try:
            u_encoded = u_match.group(1)
            u_encoded = u_encoded.replace('-', '+').replace('_', '/')
            padding = 4 - len(u_encoded) % 4
            if padding != 4:
                u_encoded += '=' * padding
            decoded = base64.b64decode(u_encoded).decode('utf-8', errors='replace')
            if decoded.startswith('http'):
                return decoded
        except Exception:
            pass
    return url


well_known_ports = {
    20: "FTP-Data(数据端口)",
    21: "FTP-Control(控制端口)",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    465: "SMTPS",
    587: "SMTP-MSA",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
    27017: "MongoDB",
}
"""常用端口映射表 - 小健 2026-05-18 从 network_tools.py 下沉"""


async def _create_http_client(
    timeout_sec: float = 30.0,
    proxy: Optional[str] = None,
    verify_ssl: bool = True,
    follow_redirects: bool = True,
) -> Any:
    """统一创建httpx.AsyncClient - 小健 2026-05-18

    消除 http_request/download_file/fetch_webpage 三处重复的客户端创建代码。
    统一代理配置（HTTP_PROXY/HTTPS_PROXY环境变量）、超时、SSL验证。

    Args:
        timeout_sec: 超时秒数，默认30
        proxy: 代理地址。None时从环境变量HTTPS_PROXY/HTTP_PROXY读取
        verify_ssl: 是否验证SSL证书，默认True
        follow_redirects: 是否跟随重定向，默认True

    Returns:
        httpx.AsyncClient 实例（需由调用方 async with 使用）
    """
    import httpx

    proxy_url = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    timeout = httpx.Timeout(timeout_sec, connect=timeout_sec)

    return httpx.AsyncClient(
        verify=verify_ssl,
        timeout=timeout,
        limits=limits,
        follow_redirects=follow_redirects,
        proxy=proxy_url if proxy_url else None,
    )
