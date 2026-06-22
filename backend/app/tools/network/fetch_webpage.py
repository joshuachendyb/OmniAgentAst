# -*- coding: utf-8 -*-
"""
N3: fetch_webpage — 获取和处理网页内容

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _extract_html_content / _build_media_result / _fetch_via_playwright 辅助函数
"""

import base64
import time as _time_mod
from typing import Any, Dict, Optional, Tuple

import re
import socket
import time
from urllib.parse import urlparse

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client
from app.utils.common_patterns import HTML_TAG_PATTERN, SCRIPT_TAG_PATTERN, STYLE_TAG_PATTERN, MULTI_WHITESPACE_PATTERN
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.utils.logger import logger
from app.constants import (
    BROWSER_USER_AGENT,
    ERR_INVALID_URL,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_JS_RENDER,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NET_UNKNOWN,
)


def _check_network() -> Dict[str, Any]:
    """检查网络连通性 — 小欧 2026-06-22"""
    test_hosts = [("dns.google", 53), ("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in test_hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            t1 = time.time()
            sock.connect((host, port))
            latency = (time.time() - t1) * 1000
            sock.close()
            return {"connected": True, "host": host, "latency_ms": round(latency, 2)}
        except (socket.timeout, socket.error, OSError):
            continue
    return {"connected": False}


def _validate_url(url: str) -> Dict[str, Any]:
    """验证URL格式 — 小欧 2026-06-22"""
    try:
        parsed = urlparse(url)
        is_valid = bool(parsed.scheme) and bool(parsed.netloc)
        valid_schemes = {"http", "https", "ftp", "ftps", "ws", "wss"}
        scheme_ok = parsed.scheme in valid_schemes
        return {"valid": is_valid and scheme_ok, "scheme": parsed.scheme, "netloc": parsed.netloc, "path": parsed.path}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def _html_to_markdown(html: str) -> str:
    """简易HTML转Markdown — 小欧 2026-06-22"""
    text = html
    text = SCRIPT_TAG_PATTERN.sub('', text)
    text = STYLE_TAG_PATTERN.sub('', text)
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
    text = HTML_TAG_PATTERN.sub(' ', text)
    text = MULTI_WHITESPACE_PATTERN.sub(' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def _build_fetch_webpage_llm_data(
    exec_code: str, duration_ms: int, url: str = "", extract_format: str = "markdown",
    status_code: int = 0, truncated: bool = False, content_preview: str = "",
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """fetch_webpage的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"获取网页失败: {url}",
            "action": {"tool": "fetch_webpage", "tool_zh": "获取网页", "target": url, "params": {"url": url, "extract_format": extract_format}},
            "status": {"exec_code": "error", "message": "获取网页失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"成功获取网页内容({extract_format}格式)" + ("(已截断)" if truncated else ""),
        "action": {"tool": "fetch_webpage", "tool_zh": "获取网页", "target": url, "params": {"url": url, "extract_format": extract_format}},
        "status": {"exec_code": "success", "message": "获取网页内容成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"status_code": {"value": status_code, "text": f"HTTP {status_code}"}},
    }


def _extract_html_content(html_content: str, extract_format: str, max_tokens: int) -> Tuple[str, bool]:
    """3路格式提取+截断检查 — 小欧 2026-06-22"""
    if extract_format == "html":
        content = html_content
    elif extract_format == "text":
        content = SCRIPT_TAG_PATTERN.sub('', html_content)
        content = STYLE_TAG_PATTERN.sub('', content)
        content = HTML_TAG_PATTERN.sub(' ', content)
        content = MULTI_WHITESPACE_PATTERN.sub(' ', content).strip()
    else:
        content = _html_to_markdown(html_content)
    max_len = max_tokens * 4
    truncated = len(content) > max_len
    if truncated:
        content = content[:max_len]
    return content, truncated


def _build_media_result(url: str, mime: str, raw_bytes: bytes, extract_format: str, response_status: int) -> Dict[str, Any]:
    """构建图片/PDF的base64附件响应 — 小欧 2026-06-22"""
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data = {
        "url": url,
        "content": f"[{mime} 文件,大小: {len(raw_bytes)} 字节]",
        "format": extract_format,
        "content_type": mime,
        "status_code": response_status,
        "truncated": False,
    }
    other_data = {
        "attachment": {
            "type": "base64",
            "mime": mime,
            "data": b64,
            "filename": url.split("/")[-1].split("?")[0] or "download",
        }
    }
    return {"data": data, "other_data": other_data}


async def _fetch_via_playwright(url: str, proxy: Optional[str], timeout_sec: float,
                                extract_format: str, max_tokens: int) -> Dict[str, Any]:
    """Playwright路径封装 — 小欧 2026-06-22"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": True, "error_detail": "js_render需要安装Playwright: pip install playwright && playwright install chromium", "params": {"url": url}, "err_code": ERR_NETWORK_JS_RENDER, "detail": "js_render需要安装Playwright"}
    try:
        browser_config = {
            "headless": True,
            "proxy": {"server": proxy} if proxy else None,
        }
        async with async_playwright() as p:
            browser = await p.chromium.launch(**browser_config)
            page = await browser.new_page()
            if proxy:
                await page.set_default_timeout(timeout_sec * 1000)
            await page.goto(url, wait_until="networkidle", timeout=timeout_sec * 1000)
            html_content = await page.content()
            await browser.close()
        content, truncated = _extract_html_content(html_content, extract_format, max_tokens)
        return {
            "html_content": html_content,
            "extracted_content": content,
            "truncated": truncated,
            "content_type": "text/html",
            "status_code": 200,
        }
    except Exception as e:
        return {"error": True, "error_detail": str(e), "params": {"url": url}, "err_code": ERR_NETWORK_JS_RENDER, "detail": str(e)}


async def fetch_webpage(
    url: str,
    prompt: Optional[str] = None,
    extract_format: str = "markdown",
    js_render: bool = False,
    timeout: int = 30000,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """获取网页内容 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    max_tokens = 8000
    timeout_sec = timeout / 1000.0
    t0 = _time_mod.perf_counter()

    try:
        url_info = _validate_url(url)
        if not url_info["valid"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_INVALID_URL, detail="URL格式无效")
            return build_error(data={"error_detail": "URL格式无效", "params": {"url": url}}, llm_data=llm_data)

        net_info = _check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用", "params": {"url": url}}, llm_data=llm_data)

        headers = {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }

        if js_render:
            playwright_result = await _fetch_via_playwright(url, proxy, timeout_sec, extract_format, max_tokens)
            if "code" in playwright_result:
                return playwright_result
            html_content = playwright_result["html_content"]
            extracted_content = playwright_result["extracted_content"]
            truncated = playwright_result["truncated"]
            content_type = playwright_result["content_type"]
            status_code = playwright_result["status_code"]
        else:
            async with create_http_client(timeout_sec=timeout_sec, proxy=proxy) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
                    logger.info(f"[fetch_webpage] Cloudflare挑战检测,降级UA重试: {url}")
                    simple_headers = dict(headers)
                    simple_headers["User-Agent"] = BROWSER_USER_AGENT
                    response = await client.get(url, headers=simple_headers)

                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower() if content_type else ""
                if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                    raw_bytes = response.content
                    media_result = _build_media_result(url, mime, raw_bytes, extract_format, response.status_code)
                    llm_data = _build_fetch_webpage_llm_data("success", 0, url, extract_format, response.status_code)
                    return build_success(data=media_result["data"], llm_data=llm_data, other_data=media_result["other_data"])

                html_content = response.text
                content_type = response.headers.get("content-type", "")

            extracted_content, truncated = _extract_html_content(html_content, extract_format, max_tokens)
            status_code = response.status_code

        result_data = {
            "url": url,
            "content": extracted_content,
            "format": extract_format,
            "content_type": content_type,
            "status_code": status_code,
            "truncated": truncated,
        }

        if prompt:
            result_data["prompt"] = prompt
            result_data["note"] = "AI提取功能需要LLM后处理"

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = truncate_data_for_frontend(result_data)
        llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, status_code, truncated)
        return build_success(data=data, llm_data=llm_data)

    except httpx.TimeoutException:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_TIMEOUT, detail=f"超时({timeout_sec:.1f}秒)")
        return build_error(data={"error_detail": f"超时({timeout_sec:.1f}秒)", "params": {"url": url, "timeout": timeout_sec}}, llm_data=llm_data)
    except httpx.HTTPStatusError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_HTTP_ERROR, detail=f"HTTP {e.response.status_code}")
        return build_error(data={"error_detail": f"HTTP {e.response.status_code}", "params": {"url": url, "status_code": e.response.status_code}}, llm_data=llm_data)
    except httpx.RequestError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_REQUEST_ERROR, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[fetch_webpage] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)