# -*- coding: utf-8 -*-
"""
网络辅助函数模块 - 网络相关的内部辅助函数

【创建时间】2026-05-17 小沈
【说明】从 support_tool/support_tool_tools.py 迁移 check_network_connectivity 和 validate_url 函数
       从 network/network_tools.py 迁移 _html_to_markdown 和 _decode_bing_redirect_url
       这些函数作为内部Helper，不注册到tool_registry，仅供Agent内部代码调用

包含函数（4个）：
- _check_network: 检查网络连通性（内部Helper）
- _validate_url: 验证URL格式（内部Helper）
- _html_to_markdown: 简易HTML转Markdown（内部Helper）- 小沈 2026-05-17
- _decode_bing_redirect_url: 解码Bing跳转URL（内部Helper）- 小沈 2026-05-17

Author: 小沈 - 2026-05-17
"""

import base64
import re
import socket
import time
from typing import Dict, Any
from urllib.parse import urlparse


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
            return {"code": "SUCCESS", "data": {"connected": True, "host": host, "latency_ms": round(latency, 2)}, "message": f"网络连通，延迟: {latency:.1f}ms"}
        except (socket.timeout, socket.error, OSError):
            continue

    return {"code": "SUCCESS", "data": {"connected": False}, "message": "网络不可用"}


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

        return {
            "code": "SUCCESS",
            "data": {
                "valid": is_valid and scheme_ok,
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "path": parsed.path,
            },
            "message": "URL格式有效" if (is_valid and scheme_ok) else "URL格式无效"
        }
    except Exception as e:
        return {"code": "SUCCESS", "data": {"valid": False, "error": str(e)}, "message": f"URL验证失败: {str(e)}"}


__all__ = [
    "_check_network",
    "_validate_url",
    "_html_to_markdown",
    "_decode_bing_redirect_url",
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
