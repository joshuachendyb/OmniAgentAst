# -*- coding: utf-8 -*-
"""
N3: fetchpage — 获取和处理网页内容

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _extract_html_content / _build_media_result / _fetch_via_playwright 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import base64
import re
import time as _time_mod
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client
from app.tools.network.network_register import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy
from app.tools.validate.timeout_validator import validate_timeout

from app.utils.common_patterns import HTML_TAG_PATTERN, SCRIPT_TAG_PATTERN, STYLE_TAG_PATTERN, MULTI_WHITESPACE_PATTERN
from app.utils.logger import logger
from app.tools.tool_constants import TOOL_BROWSER_UA
from app.tools.tool_constants import (
    ERR_INVALID_URL,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_JS_RENDER,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NET_UNKNOWN,
)


_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr",
})


class _ContentExtractor(HTMLParser):
    """用HTMLParser正确提取匹配指定属性的容器内容(处理嵌套标签)—小欧2026-06-23"""

    def __init__(self, tag_matchers: List[tuple]):
        super().__init__(convert_charrefs=False)
        self._tag_matchers = tag_matchers
        self._depth = 0
        self._started = False
        self._parts: List[str] = []
        self._found: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if self._started:
            if tag not in _VOID_ELEMENTS:
                self._depth += 1
            self._parts.append(self.get_starttag_text())
        elif self._found is None:
            for t, attr_dict in self._tag_matchers:
                if tag == t and self._match(dict(attrs), attr_dict):
                    self._started = True
                    self._depth = 0
                    self._parts = []
                    break

    def handle_endtag(self, tag):
        if self._started:
            if self._depth == 0 and any(tag == t for t, _ in self._tag_matchers):
                self._found = "".join(self._parts)
                self._started = False
            else:
                if self._depth > 0:
                    self._parts.append(f"</{tag}>")
                if tag not in _VOID_ELEMENTS:
                    self._depth -= 1

    def handle_startendtag(self, tag, attrs):
        if self._started:
            self._parts.append(self.get_starttag_text())

    def handle_data(self, data):
        if self._started:
            self._parts.append(data)

    def handle_entityref(self, name):
        if self._started:
            self._parts.append(f"&{name};")

    def handle_charref(self, name):
        if self._started:
            self._parts.append(f"&#{name};")

    def handle_comment(self, data):
        pass

    @staticmethod
    def _match(attrs: Dict[str, str], required: Dict[str, str]) -> bool:
        for key, val in required.items():
            actual = attrs.get(key)
            if actual is None:
                return False
            if val is True:
                continue
            if hasattr(val, "search"):
                if not val.search(actual):
                    return False
            elif val != actual:
                return False
        return True

    def get_content(self) -> Optional[str]:
        return self._found


def _extract_main_content(html: str) -> Optional[str]:
    """提取页面主要内容区域HTML — 小欧 2026-06-23

    用HTMLParser正确提取正文容器(处理嵌套标签):
    1. <article> 语义标签
    2. <main> 语义标签
    3. <div id="main">
    4. <div class~=w3-main> (w3schools典型结构)
    5. <div class/id 含 content/main/article/post/entry
    找不到则返回None。
    """
    id_main = re.compile(r'(?:^|\s)main(?:\s|$)')
    w3_main = re.compile(r'w3-main')
    content_like = re.compile(r'(?:content|main|article|post|entry)')
    tag_matchers = [
        ("article", {}),
        ("main", {}),
        ("div", {"id": "main"}),
        ("div", {"class": w3_main}),
        ("div", {"id": id_main}),
        ("div", {"class": content_like}),
    ]
    extractor = _ContentExtractor(tag_matchers)
    extractor.feed(html)
    content = extractor.get_content()
    if content:
        text_len = len(re.sub(r'<[^>]+>', "", content).strip())
        if text_len > 50:
            return content
    return None


def _html_to_markdown(html: str) -> str:
    """简易HTML转Markdown — 小欧 2026-06-22, 2026-06-23 改进:优先提取正文区域"""
    text = html
    main_content = _extract_main_content(html)
    if main_content:
        text = main_content
    text = SCRIPT_TAG_PATTERN.sub('', text)
    text = STYLE_TAG_PATTERN.sub('', text)
    text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL|re.IGNORECASE)
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
    status_code: int = 0, truncated: bool = False,
    err_code: str = "", detail: str = "", hint: str = "",
    mime_type: str = "",
    prompt: Optional[str] = None, js_render: bool = False, timeout: int = 30,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """fetch_webpage的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 过滤None值"""
    _act_params = {"url": url, "extract_format": extract_format, "js_render": js_render, "timeout": timeout}
    if prompt is not None:
        _act_params["prompt"] = prompt
    if proxy is not None:
        _act_params["proxy"] = proxy
    if exec_code == "error":
        return {
            "summary": f"获取网页失败: {url}",
            "action": {"tool": "fetchpage", "tool_zh": "获取网页", "target": url, "params": _act_params},
            "status": {"exec_code": "error", "message": "获取网页失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查URL和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if mime_type:
        summary = f"成功获取{mime_type}文件"
    else:
        summary = f"成功获取网页内容({extract_format}格式)"
    if truncated:
        summary += "(已截断)"
    return {
        "summary": summary,
        "action": {"tool": "fetchpage", "tool_zh": "获取网页", "target": url, "params": _act_params},
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


async def _fetch_via_playwright(url: str, proxy: Optional[str], timeout: float,
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
            try:
                page = await browser.new_page()
                if proxy:
                    await page.set_default_timeout(timeout * 1000)
                await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                current_url = page.url
                if current_url and current_url != url:
                    is_valid, err, _ = validate_url(current_url)
                    if not is_valid:
                        logger.warning(f"[fetchpage] Playwright重定向到不安全地址: {err}")
                        return {"error": True, "error_detail": f"重定向到不安全地址: {err or 'URL无效'}", "params": {"url": url}, "err_code": ERR_INVALID_URL, "detail": err}
                html_content = await page.content()
            finally:
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


async def fetchpage(
    url: str,
    prompt: Optional[str] = None,
    extract_format: str = "markdown",
    js_render: bool = False,
    timeout: int = 30,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """获取网页内容 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    max_tokens = 8000
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "fetchpage")
    if not timeout_valid:
        llm_data = _build_fetch_webpage_llm_data("error", 0, url, extract_format, err_code=ERR_INVALID_URL, detail=timeout_err, hint="请检查超时设置", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={"error_detail": timeout_err, "params": {"url": url, "timeout": timeout}}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_fetch_webpage_llm_data("error", 0, url, extract_format, err_code=ERR_INVALID_URL, detail=proxy_err, hint="请检查代理配置", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={"error_detail": proxy_err, "params": {"proxy": proxy}}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()

    try:
        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_INVALID_URL, detail=error_msg or "URL格式无效", hint="请检查URL格式", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
            return build_error(data={"error_detail": error_msg or "URL格式无效", "params": {"url": url}}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[fetchpage] {warning_msg}")

        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_DOWN, detail="网络不可用", hint="请检查网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
            return build_error(data={"error_detail": "网络不可用", "params": {"url": url}}, llm_data=llm_data)

        headers = {
            "User-Agent": TOOL_BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }

        if js_render:
            playwright_result = await _fetch_via_playwright(url, proxy, timeout, extract_format, max_tokens)
            if playwright_result.get("error"):
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=playwright_result.get("err_code", ERR_NETWORK_JS_RENDER), detail=playwright_result.get("detail", ""), hint="请检查网站是否支持JS渲染", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
                return build_error(data={"error_detail": playwright_result.get("error_detail", ""), "params": playwright_result.get("params", {})}, llm_data=llm_data)
            html_content = playwright_result["html_content"]
            extracted_content = playwright_result["extracted_content"]
            truncated = playwright_result["truncated"]
            content_type = playwright_result["content_type"]
            status_code = playwright_result["status_code"]
        else:
            async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
                    logger.info(f"[fetchpage] Cloudflare挑战检测,降级UA重试: {url}")
                    simple_headers = dict(headers)
                    simple_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    response = await client.get(url, headers=simple_headers)

                response.raise_for_status()

                MAX_FETCH_CONTENT_LENGTH = 100 * 1024 * 1024
                cl = response.headers.get("content-length")
                if cl and int(cl) > MAX_FETCH_CONTENT_LENGTH:
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    return build_error(data={"error_detail": f"内容过大({int(int(cl)/1024/1024)}MB),限制{MAX_FETCH_CONTENT_LENGTH//(1024*1024)}MB", "params": {"url": url, "content_length": int(cl)}}, llm_data=_build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_REQUEST_ERROR, detail=f"内容过大({int(int(cl)/1024/1024)}MB)", hint="请使用更具体的URL或减少内容", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy))

                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower() if content_type else ""
                if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                    raw_bytes = response.content
                    media_result = _build_media_result(url, mime, raw_bytes, extract_format, response.status_code)
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, response.status_code, mime_type=mime, prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
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
        llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, status_code, truncated, prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        # ---- observation_formatter route -------------------------------------------
        # branch: #2 raw str
        # trigger: "content" in data and isinstance(data["content"], str)
        # handler: inline — 直接返回 data["content"], OBS_MAX_STRING_LENGTH 截断
        # file:    observation_formatter.py:117-122
        # ------------------------------------------------------------------------------
        return build_success(data=result_data, llm_data=llm_data)

    except httpx.TimeoutException:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_TIMEOUT, detail=f"超时({timeout:.1f}秒)", hint="请检查URL和网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={"error_detail": f"超时({timeout:.1f}秒)", "params": {"url": url, "timeout": timeout}}, llm_data=llm_data)
    except httpx.HTTPStatusError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_HTTP_ERROR, detail=f"HTTP {e.response.status_code}", hint="请检查URL和服务器状态", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={"error_detail": f"HTTP {e.response.status_code}", "params": {"url": url, "status_code": e.response.status_code}}, llm_data=llm_data)
    except httpx.RequestError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_REQUEST_ERROR, detail=str(e), hint="请检查URL和网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[fetchpage] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NET_UNKNOWN, detail=str(e), hint="请检查URL和网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)