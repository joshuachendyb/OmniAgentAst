# -*- coding: utf-8 -*-
"""
Network 工具函数模块 - 网络通信工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- http_request: 发起HTTP请求
- download_file: 下载文件到本地
- fetch_webpage: 获取和处理网页内容
- search_web: 搜索网络获取最新信息
- ping: 执行ping测试（小沈 2026-05-02）
- port_check: 检查端口是否开放（小沈 2026-05-02）

返回格式：统一 {code, data, message} 格式
- code: SUCCESS 或 ERR_xxx 错误码
- data: 成功时返回数据，失败时为 None
- message: 描述信息

Author: 小沈 - 2026-04-29
"""

import os
import json
import re
import platform
import subprocess
import socket
import asyncio
from typing import Optional, Dict, Any, Literal, List
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from app.utils.logger import logger
from app.services.tools.toolhelper.network_helper import well_known_ports  # 小健 2026-05-18
from app.services.tools.tool_result_utils import build_next_actions, truncate_data_for_frontend, make_json_safe  # 小沈 2026-05-20
from app.services.tools._response import build_success, build_error


async def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 30000,
    proxy: Optional[str] = None,
    retry: int = 3,
) -> dict:
    """发起HTTP请求 — 小沈 2026-05-19 精简参数(11→8)"""
    # 参数校验
    if retry < 0 or retry > 10:
        return build_error("ERR_NETWORK_INVALID_PARAM", f"重试次数必须在0-10之间，当前值：{retry}")
    
    timeout_sec = timeout / 1000.0
    
    try:
        from app.services.tools.toolhelper.network_helper import _validate_url, _check_network

        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            return build_error("ERR_INVALID_URL", f"URL格式无效: {url}，URL必须包含协议和域名（如 https://api.example.com/data）")

        net_info = _check_network()
        if not net_info["data"]["connected"]:
            return build_error("ERR_NETWORK_DOWN", "网络不可用，无法发送请求")

        parsed = urlparse(url)
        if params:
            query_string = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=query_string))

        request_headers = {}
        if headers:
            request_headers.update(headers)

        proxy_config = None
        if proxy:
            proxy_config = proxy
        elif os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"):
            proxy_config = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

        last_exception = None
        for attempt in range(retry + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout_sec),
                    follow_redirects=True,
                    verify=True,
                    proxy=proxy_config,
                ) as client:
                    method_upper = method.upper()

                    request_kwargs = {
                        "url": url,
                        "headers": request_headers,
                    }

                    if method_upper in ("POST", "PUT", "PATCH"):
                        if json_body is not None:
                            request_kwargs["json"] = json_body

                    response = await client.request(method_upper, **request_kwargs)
                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")
                    response_body = None
                    if "application/json" in content_type:
                        try:
                            response_body = response.json()
                        except (json.JSONDecodeError, ValueError):
                            response_body = response.text
                    else:
                        response_body = response.text

                    # 【修复 小健 2026-05-16】llm_data给LLM关键数据，≤5K全给，超5K用make_json_safe保留结构
                    _body = response_body
                    _body_json_len = 0
                    if isinstance(response_body, (dict, list)):
                        _body_json_len = len(json.dumps(response_body, ensure_ascii=False))
                    _ct = response.headers.get("content-type", "")
                    _ct_short = _ct.split(";")[0].strip() if _ct else "unknown"

                    if isinstance(_body, str) and len(_body) > 5000:
                        try:
                            json.loads(_body)
                        except (json.JSONDecodeError, ValueError):
                            _body = _body[:4000] + f"\n...[截断 {len(_body)-4000} 字符]"

                    if isinstance(response_body, dict) and _body_json_len <= 5000:
                        _llm_body = response_body
                    elif isinstance(response_body, list) and _body_json_len <= 5000:
                        _llm_body = response_body
                    elif isinstance(response_body, str) and len(response_body) <= 5000:
                        _llm_body = response_body
                    elif isinstance(response_body, (dict, list)):
                        from app.services.tools.tool_result_utils import make_json_safe
                        _llm_body = make_json_safe(response_body, max_depth=4, max_str_len=500)
                    else:
                        _llm_body = str(_body)[:4000]

                    return build_success(
                        truncate_data_for_frontend({
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                            "body": _body,
                        }),
                        f"请求成功 (HTTP {response.status_code})",
                        llm_data={
                            "状态码": response.status_code,
                            "内容类型": _ct_short,
                            "响应体": _llm_body,
                        },
                        next_actions=build_next_actions([("http_request", "继续发送请求", "需要发送更多请求时")]),
                    )
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exception = e
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in (429, 500, 502, 503, 504):
                    try:
                        error_body = e.response.text
                    except Exception:
                        error_body = None
                    return build_error(
                        "ERR_NETWORK_HTTP_ERROR",
                        f"HTTP请求失败 (HTTP {e.response.status_code})：{url}",
                        data={
                            "status_code": e.response.status_code,
                            "body": error_body,
                        },
                    )
                if attempt < retry:
                    import asyncio
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                break

        if isinstance(last_exception, httpx.TimeoutException):
            return build_error("ERR_NETWORK_TIMEOUT", f"请求超时（{timeout}毫秒）：{url}")
        elif isinstance(last_exception, httpx.HTTPStatusError):
            return build_error(
                "ERR_NETWORK_HTTP_ERROR",
                f"HTTP请求失败（重试{retry}次后）：{url}",
                data={
                    "status_code": last_exception.response.status_code,
                    "body": last_exception.response.text if hasattr(last_exception.response, 'text') else None,
                },
            )
        else:
            return build_error("ERR_NETWORK_REQUEST_ERROR", f"网络请求失败（重试{retry}次后）：{str(last_exception)}")

    except Exception as e:
        logger.error(f"[http_request] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"请求异常: {str(e)}")


async def download_file(
    url: str,
    destination_path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 300000,
    proxy: Optional[str] = None,
) -> dict:
    """从URL下载文件 — 小沈 2026-05-19 精简参数(7→5)"""
    # ⚠️ 警告: 以下参数已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    resume = False
    chunk_size = 8192
    try:
        from app.services.tools.toolhelper.network_helper import _validate_url, _check_network

        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            return build_error("ERR_INVALID_URL", f"URL格式无效: {url}，URL必须包含协议和域名")

        net_info = _check_network()
        if not net_info["data"]["connected"]:
            return build_error("ERR_NETWORK_DOWN", "网络不可用，无法发送请求")

        # 验证目标路径
        dest_path = os.path.abspath(destination_path)
        dest_dir = os.path.dirname(dest_path)
        if not dest_dir:
            return build_error("ERR_NETWORK_INVALID_PATH", f"无效的目标路径: {destination_path}，路径必须包含目录")

        # 创建目标目录
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            return build_error("ERR_NETWORK_CREATE_DIR", f"无法创建目录 {dest_dir}: {str(e)}")

        # 构建请求头
        request_headers = {}
        if headers:
            request_headers.update(headers)

        # 代理配置 - 小健 2026-05-18 添加
        proxy_config = None
        if proxy:
            proxy_config = proxy
        elif os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"):
            proxy_config = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

        # 检查是否支持断点续传（根据resume参数和文件是否存在）
        downloaded = 0
        resume_offset = 0
        if resume and os.path.exists(dest_path):
            resume_offset = os.path.getsize(dest_path)
            if resume_offset > 0:
                request_headers["Range"] = f"bytes={resume_offset}-"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout / 1000.0, connect=timeout / 1000.0 / 3),  # 小健 2026-05-19: 毫秒转秒+添加connect超时
            follow_redirects=True,
            proxy=proxy_config
        ) as client:
            async with client.stream("GET", url, headers=request_headers) as response:
                response.raise_for_status()
                # 检查服务器是否支持断点续传
                is_resume = response.status_code == 206
                if is_resume:
                    content_range = response.headers.get("content-range", "")
                    try:
                        if content_range and "/" in content_range:
                            total_size = int(content_range.split("/")[-1])
                        else:
                            total_size = resume_offset + int(response.headers.get("content-length", 0))
                    except (ValueError, IndexError):
                        total_size = resume_offset + int(response.headers.get("content-length", 0))
                else:
                    total_size = int(response.headers.get("content-length", 0))
                    if resume_offset > 0:
                        resume_offset = 0

                content_type = response.headers.get("content-type", "")

                # 流式写入文件
                progress_percent = 0
                try:
                    with open(dest_path, "ab" if resume_offset > 0 else "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress_percent = int((resume_offset + downloaded) * 100 / total_size)
                except (PermissionError, OSError) as e:
                    # 清理不完整的文件
                    try:
                        if dest_path and os.path.exists(dest_path):
                            os.remove(dest_path)
                    except OSError:
                        pass
                    return build_error("ERR_NETWORK_WRITE_FILE", f"写入文件失败 {dest_path}: {str(e)}")

                return build_success(
                    {
                        "file_path": dest_path,
                        "file_size": downloaded,
                        "total_size": total_size,
                        "progress_percent": progress_percent,
                        "content_type": content_type,
                    },
                    f"文件下载成功 ({downloaded}/{total_size} 字节, {progress_percent}%)：保存到 {dest_path}",
                    llm_data={"路径": dest_path, "大小": downloaded, "类型": content_type},
                    next_actions=build_next_actions([("read_file", "读取下载的文件", "需要查看下载内容时")]),
                )

    except httpx.TimeoutException:
        return build_error("ERR_NETWORK_TIMEOUT", f"下载超时（{timeout/1000}秒）：{url}")
    except httpx.HTTPStatusError as e:
        return build_error("ERR_NETWORK_HTTP_ERROR", f"下载失败 (HTTP {e.response.status_code})：{url}")
    except httpx.RequestError as e:
        return build_error("ERR_NETWORK_REQUEST_ERROR", f"网络请求失败：{str(e)}")
    except Exception as e:
        logger.error(f"[download_file] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"下载异常: {str(e)}")


async def fetch_webpage(
    url: str,
    prompt: Optional[str] = None,
    extract_format: str = "markdown",
    js_render: bool = False,
    timeout: int = 30000,
    max_tokens: int = 8000,
    proxy: Optional[str] = None,
) -> dict:
    """获取网页内容 — 小沈 2026-05-19 精简参数(8→7)"""
    timeout_sec = timeout / 1000.0
    
    try:
        from app.services.tools.toolhelper.network_helper import _validate_url, _check_network

        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            return build_error("ERR_INVALID_URL", f"URL格式无效: {url}")

        net_info = _check_network()
        if not net_info["data"]["connected"]:
            return build_error("ERR_NETWORK_DOWN", "网络不可用，无法发送请求")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        headers["Accept-Language"] = "en-US,en;q=0.9,zh-CN;q=0.8"
        headers["Accept-Encoding"] = "gzip, deflate"
        
        # js_render: 使用Playwright渲染动态页面
        if js_render:
            try:
                from playwright.async_api import async_playwright
                
                # Playwright proxy格式: {"server": "http://proxy:port"} - 小健 2026-05-18 修正
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
                    status_code = 200
                    
                    await browser.close()
                    
                    # 提取内容 - 小沈 2026-05-05 修正js_render分支缺少内容提取
                    if extract_format == "html":
                        extracted_content = html_content
                    elif extract_format == "text":
                        text_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL|re.IGNORECASE)
                        text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL|re.IGNORECASE)
                        text_content = re.sub(r'<[^>]+>', ' ', text_content)
                        text_content = re.sub(r'\s+', ' ', text_content).strip()
                        extracted_content = text_content
                    else:
                        extracted_content = _html_to_markdown(html_content)
                    
                    if len(extracted_content) > max_tokens * 4:
                        extracted_content = extracted_content[:max_tokens * 4]
                        truncated = True
                    else:
                        truncated = False
                    
                    content_type = "text/html"
                    
            except ImportError:
                return build_error("ERR_NETWORK_JS_RENDER", "js_render需要安装Playwright: pip install playwright && playwright install chromium")
            except Exception as e:
                return build_error("ERR_NETWORK_JS_RENDER", f"JS渲染失败: {str(e)}")
        else:
            # httpx 0.26.0: proxy参数接受str，proxies已弃用 - 小健 2026-05-18 修正
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_sec),
                follow_redirects=True,
                proxy=proxy
            ) as client:
                response = await client.get(url, headers=headers)
                
                # 【修复 2026-05-16 小健】Cloudflare反爬检测：cf-mitigated → 降级UA重试
                if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
                    logger.info(f"[fetch_webpage] Cloudflare挑战检测，降级UA重试: {url}")
                    simple_headers = dict(headers)
                    simple_headers["User-Agent"] = "opencode/1.0"
                    response = await client.get(url, headers=simple_headers)
                
                response.raise_for_status()
                
                # 【修复 2026-05-16 小健】图片类型 → 返回base64附件
                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower() if content_type else ""
                if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                    raw_bytes = response.content
                    import base64
                    b64 = base64.b64encode(raw_bytes).decode("ascii")
                    return build_success(
                        {
                            "url": url,
                            "content": f"[{mime} 文件，大小: {len(raw_bytes)} 字节]",
                            "format": extract_format,
                            "content_type": content_type,
                            "status_code": response.status_code,
                            "truncated": False,
                        },
                        f"成功获取{mime}文件",
                        attachment={
                            "type": "base64",
                            "mime": mime,
                            "data": b64,
                            "filename": url.split("/")[-1].split("?")[0] or "download"
                        },
                        next_actions=build_next_actions([("search_web", "搜索更多网页", "需要搜索更多信息时")]),
                    )
                
                html_content = response.text
                content_type = response.headers.get("content-type", "")
            
            # 提取内容
            if extract_format == "html":
                extracted_content = html_content
            elif extract_format == "text":
                text_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL|re.IGNORECASE)
                text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL|re.IGNORECASE)
                text_content = re.sub(r'<[^>]+>', ' ', text_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                extracted_content = text_content
            else:
                extracted_content = _html_to_markdown(html_content)
            
            if len(extracted_content) > max_tokens * 4:
                extracted_content = extracted_content[:max_tokens * 4]
                truncated = True
            else:
                truncated = False
            
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
        
        _content_for_llm = result_data.get("content", "")
        if isinstance(_content_for_llm, str) and len(_content_for_llm) > 5000:
            _content_for_llm = _content_for_llm[:5000] + f"...(原文{len(_content_for_llm)}字符)"
        
        return build_success(
            truncate_data_for_frontend(result_data),
            f"成功获取网页内容（{extract_format}格式）" + ("（已截断）" if truncated else ""),
            llm_data={
                "URL": url, "格式": extract_format, "状态码": result_data.get("status_code"),
                "内容预览": _content_for_llm, "截断": truncated
            },
            next_actions=build_next_actions([("search_web", "搜索更多网页", "需要搜索更多信息时")]),
        )
    
    except httpx.TimeoutException:
        return build_error("ERR_NETWORK_TIMEOUT", f"获取网页超时（{timeout_sec:.1f}秒）：{url}")
    except httpx.HTTPStatusError as e:
        return build_error("ERR_NETWORK_HTTP_ERROR", f"获取网页失败 (HTTP {e.response.status_code})：{url}")
    except httpx.RequestError as e:
        return build_error("ERR_NETWORK_REQUEST_ERROR", f"网络请求失败：{str(e)}")
    except Exception as e:
        logger.error(f"[fetch_webpage] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"获取网页异常: {str(e)}")


def _html_to_markdown(html: str) -> str:
    """简单的HTML转Markdown - 小沈 2026-05-02"""
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

async def _search_mcp_engine(engine: str, query: str, num_results: int, proxy: Optional[str] = None) -> Optional[List[dict]]:
    """MCP搜索引擎统一入口 - 小沈 2026-05-17
    合并 _search_parallel_mcp + _search_exa_mcp，消除约80行重复代码。
    
    Args:
        engine: "parallel" | "exa"
        query: 搜索关键词
        num_results: 结果数量
        proxy: 代理服务器地址（小沈 2026-05-19 修复：新增proxy参数）
    
    Returns:
        搜索结果列表或None（失败时）
    """
    MCP_CONFIGS = {
        "parallel": {
            "url": "https://search.parallel.ai/mcp",
            "tool_name": "web_search",
            "build_args": lambda q, n: {
                "objective": q,
                "search_queries": [q],
                "session_id": "omniagent-search",
            },
        },
        "exa": {
            "url": "https://mcp.exa.ai/mcp",
            "tool_name": "web_search_exa",
            "build_args": lambda q, n: {
                "query": q,
                "type": "auto",
                "numResults": n,
                "livecrawl": "fallback",
            },
        },
    }
    config = MCP_CONFIGS.get(engine)
    if not config:
        return None
    
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": config["tool_name"],
            "arguments": config["build_args"](query, num_results),
        }
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0), proxy=proxy) as c:
            resp = await c.post(
                config["url"],
                json=payload,
                headers={"Accept": "application/json, text/event-stream"}
            )
            resp.raise_for_status()
            data = resp.json()
            result_text = data.get("result", {}).get("content", [{}])[0].get("text", "")
            if not result_text:
                logger.info(f"[_search_mcp_engine:{engine}] 返回空数据")
                return None
        
        if engine == "parallel":
            if not result_text.startswith("{"):
                logger.info("[_search_mcp_engine:parallel] 返回数据非JSON")
                return None
            parsed = json.loads(result_text)
            raw_results = parsed.get("results", [])
            results = []
            for r in raw_results[:num_results]:
                url = r.get("url", "")
                title = r.get("title", "")
                excerpts = r.get("excerpts", [])
                snippet = excerpts[0][:300] if excerpts else ""
                if title and url:
                    results.append({"title": title, "url": url, "snippet": snippet, "source": "Parallel"})
            if results:
                return results
            logger.info("[_search_mcp_engine:parallel] 无搜索结果")
            return None
        
        else:  # exa
            results = []
            current = {}
            for line in result_text.split("\n"):
                line = line.strip()
                if line.startswith("Title: "):
                    if current.get("title"):
                        results.append(current)
                        if len(results) >= num_results:
                            break
                    current = {"title": line[7:], "url": "", "snippet": ""}
                elif line.startswith("URL: "):
                    current["url"] = line[5:]
                elif line.startswith("Highlights:") or (current.get("snippet") == "" and line and not line.startswith("Published") and not line.startswith("Author")):
                    if not current["snippet"]:
                        current["snippet"] = line[:300]
            if current.get("title"):
                results.append(current)
            formatted = []
            for r in results[:num_results]:
                if r.get("title") and r.get("url"):
                    formatted.append({"title": r["title"], "url": r["url"], "snippet": r.get("snippet", "")[:300], "source": "Exa"})
            if formatted:
                return formatted
            logger.info("[_search_mcp_engine:exa] 无搜索结果")
            return None
    
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
        logger.info(f"[_search_mcp_engine:{engine}] 失败: {type(e).__name__}")
        return None
    except Exception as e:
        logger.info(f"[_search_mcp_engine:{engine}] 异常: {type(e).__name__}")
        return None


async def _search_parallel_mcp(query: str, num_results: int, proxy: Optional[str] = None) -> Optional[List[dict]]:
    """Parallel MCP搜索 - 小健 2026-05-16
    【2026-05-17 小沈 已弃用】请使用 _search_mcp_engine("parallel", query, num_results, proxy) 代替
    """
    return await _search_mcp_engine("parallel", query, num_results, proxy)


async def _search_exa_mcp(query: str, num_results: int, proxy: Optional[str] = None) -> Optional[List[dict]]:
    """Exa MCP搜索 - 小健 2026-05-16
    【2026-05-17 小沈 已弃用】请使用 _search_mcp_engine("exa", query, num_results, proxy) 代替
    """
    return await _search_mcp_engine("exa", query, num_results, proxy)


def _decode_bing_redirect_url(url: str) -> str:
    """
    解码Bing ck/a跳转链接，提取真实URL - 小健 2026-05-16
    Bing使用 https://www.bing.com/ck/a?!&&p=<hash>&u=<base64_url> 格式的跳转链接
    """
    if "bing.com/ck/a" not in url:
        return url
    # 尝试从u参数提取base64编码的真实URL
    u_match = re.search(r'[?&]u=([^&]+)', url)
    if u_match:
        try:
            import base64
            u_encoded = u_match.group(1)
            # URL安全的base64
            u_encoded = u_encoded.replace('-', '+').replace('_', '/')
            # 补全base64填充
            padding = 4 - len(u_encoded) % 4
            if padding != 4:
                u_encoded += '=' * padding
            decoded = base64.b64decode(u_encoded).decode('utf-8', errors='replace')
            if decoded.startswith('http'):
                return decoded
        except Exception:
            pass
    return url


async def search_web(
    query: str,
    allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None,
    num_results: int = 10,
    proxy: Optional[str] = None,
) -> dict:
    """搜索网络 — 小沈 2026-05-19 精简参数(7→5)"""
    try:
        if len(query) < 2:
            return build_error("ERR_PARAM_INVALID", "搜索查询至少需要2个字符")
        
    # ===== 第一引擎：Parallel MCP =====
        results = await _search_parallel_mcp(query, num_results, proxy)
        engine_used = "Parallel"
        
        # ===== 第二引擎：Exa MCP =====
        if results is None:
            logger.info("[search_web] Parallel失败，降级到Exa MCP搜索")
            results = await _search_exa_mcp(query, num_results, proxy)
            engine_used = "Exa"
        
        # ===== 第三引擎：Bing中国 =====
        if results is None:
            logger.info("[search_web] Exa失败，降级到Bing中国搜索")
            try:  # 小健 2026-05-19: 包裹try/except, Bing网络错误不应导致整个search_web崩溃
                results = await _search_bing(query, num_results, proxy)
                engine_used = "Bing"
            except Exception as e:
                logger.warning(f"[search_web] Bing搜索也失败: {e}")
                results = []
        
        # 域名过滤
        if allowed_domains:
            results = [r for r in results if any(domain in r.get("url", "") for domain in allowed_domains)]
        if blocked_domains:
            results = [r for r in results if not any(domain in r.get("url", "") for domain in blocked_domains)]
        
        results = results[:num_results]
        
        # 解码所有结果中的ck/a跳转URL
        for r in results:
            r["url"] = _decode_bing_redirect_url(r.get("url", ""))
            
        # 整理llm_data展示结果
        llm_results = []
        for r in results:
            raw_url = r.get("url", "")
            clean_url = _decode_bing_redirect_url(raw_url)
            llm_results.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", "")[:300],
                "url": clean_url,
                "source": r.get("source", ""),
            })

        return build_success(
            {
                "query": query,
                "results": results,
                "total": len(results),
                "engine": engine_used,
            },
            f"找到 {len(results)} 条搜索结果（{engine_used}）",
            llm_data={
                "搜索引擎": engine_used,
                "查询词": query,
                "结果数量": len(results),
                "搜索结果": llm_results if llm_results else "无相关结果",
            },
            next_actions=build_next_actions([("fetch_webpage", "打开搜索结果链接", "需要查看某个搜索结果的详细内容时")]),
        )
    
    except Exception as e:
        logger.error(f"[search_web] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"搜索异常: {str(e)}")


async def _search_bing(
    query: str,
    num_results: int,
    proxy_config: Optional[str] = None,
) -> List[dict]:
    """Bing搜索（HTML解析）- 小沈 2026-05-07, 小健 2026-05-19 proxy_config改字符串
    国内可访问，无需API Key，解析搜索结果页HTML
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    params = {"q": query, "count": num_results}
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=8.0),
        follow_redirects=True,
        proxy=proxy_config  # 小健 2026-05-19: proxies→proxy(httpx 0.26.0已弃用proxies)
    ) as client:
        response = await client.get("https://cn.bing.com/search", params=params, headers=headers)
        response.raise_for_status()
        html = response.text
    
    results = []
    # Bing搜索结果在 <li class="b_algo"> 块中
    # URL在 <a href="..."> 中，标题在 <h2> 中，摘要在 <p> 或 <div class="b_caption"><p> 中
    algo_blocks = re.split(r'<li\s+class="b_algo"', html)
    for block in algo_blocks[1:]:
        if len(results) >= num_results:
            break
        # 提取URL：优先找非bing.com的外部链接，其次是bing.com/ck/a跳转链接
        a_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', block[:3000])
        if not a_match:
            continue
        url = a_match.group(1)
        # 【2026-05-13 小沈】Bing现在所有结果都用ck/a跳转链接，没有直接外部URL
        # HTTP跟随跳转会返回原URL（无法解码），所以直接保留ck/a链接作为结果
        if "bing.com/ck/a" in url:
            # 保留跳转链接，用户点击后会被重定向到真实网站
            pass
        elif "bing.com" in url or "microsoft.com" in url:
            continue
        
        # 提取标题：优先从<h2>取（Bing的真实标题在h2中）
        h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block[:3000], re.DOTALL)
        if h2_match:
            title = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()
        else:
            # 兜底从<a>取
            a_text_match = re.search(r'<a[^>]+href="[^"]+ "[^>]*>(.*?)</a>', block[:3000], re.DOTALL)
            title = re.sub(r'<[^>]+>', '', a_text_match.group(1)).strip() if a_text_match else ""
        # 提取摘要
        snippet = ""
        p_match = re.search(r'<div\s+class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
        if not p_match:
            p_match = re.search(r'<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
        if p_match:
            snippet = re.sub(r'<[^>]+>', '', p_match.group(1)).strip()
            snippet = re.sub(r'&ensp;|&#\d+;', ' ', snippet).strip()
        
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet, "source": "Bing"})
    
    if not results:
        logger.warning("[_search_bing] 主解析未提取到结果，尝试简易模式")
        href_pattern = re.compile(r'<a\s+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        for match in href_pattern.finditer(html):
            url = match.group(1)
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if "bing.com/ck/a" in url:
                pass  # 保留跳转链接
            elif "bing.com" in url or "microsoft.com" in url:
                continue
            if title and len(title) > 5:
                results.append({"title": title, "url": url, "snippet": "", "source": "Bing"})
            if len(results) >= num_results:
                break
    
    return results


async def _ping(
    host: str,
    count: int = 4,
    timeout: int = 5,
) -> dict:
    """
    执行ping测试 - 小沈 2026-05-02
    
    使用系统ping命令测试网络连通性。
    Windows使用 ping 命令，Linux/macOS使用 ping 命令。
    
    参数:
        host: 目标主机地址（域名或IP）
        count: 发送ping包数量
        timeout: 每次ping的超时时间（秒）
    
    返回:
        {
            "code": "SUCCESS",
            "data": {
                "host": "目标主机",
                "packets_sent": 发送包数,
                "packets_received": 接收包数,
                "packets_lost": 丢失包数,
                "loss_rate": 丢包率,
                "min_latency": 最小延迟(ms),
                "avg_latency": 平均延迟(ms),
                "max_latency": 最大延迟(ms),
                "is_reachable": 是否可达,
                "raw_output": 原始输出,
            },
            "message": "描述信息"
        }
    """
    try:
        if not host or len(host.strip()) == 0:
            return build_error("ERR_NETWORK_INVALID_HOST", "目标主机地址不能为空")
        
        host = host.strip()
        
        system = platform.system().lower()
        
        if system == "windows":
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=count * timeout + 10
            )
            raw_output = result.stdout
        except subprocess.TimeoutExpired:
            return build_error("ERR_NETWORK_TIMEOUT", f"Ping命令执行超时（{count * timeout + 10}秒）")
        except FileNotFoundError:
            return build_error("ERR_SHELL_COMMAND_NOT_FOUND", "系统ping命令不可用")
        
        packets_sent = count
        packets_received = 0
        packets_lost = 0
        loss_rate = 0.0
        min_latency = None
        avg_latency = None
        max_latency = None
        is_reachable = False
        
        if system == "windows":
            # 【修复 小健 2026-05-16】兼容Windows中文/英文ping丢包格式
            loss_match = re.search(r"(?:已发送|Packets\s*:\s*Sent\s*=\s*)(\d+).*?(?:已接收|Received\s*=\s*)(\d+).*?(?:丢失|Lost\s*=\s*)(\d+).*?(\d+)%", raw_output, re.DOTALL | re.IGNORECASE)
            if loss_match:
                packets_sent = int(loss_match.group(1))
                packets_received = int(loss_match.group(2))
                packets_lost = int(loss_match.group(3))
                loss_rate = float(loss_match.group(4))
            
            # 【修复 小健 2026-05-16】兼容Windows中文/英文ping延迟格式，支持小数
            latency_match = re.search(r"(?:最短|Minimum)\s*[=:]\s*([\d.]+)\s*ms.*?(?:最长|Maximum)\s*[=:]\s*([\d.]+)\s*ms.*?(?:平均|Average)\s*[=:]\s*([\d.]+)\s*ms", raw_output, re.DOTALL | re.IGNORECASE)
            if latency_match:
                min_latency = float(latency_match.group(1))
                max_latency = float(latency_match.group(2))
                avg_latency = float(latency_match.group(3))
            
            # 【修复 小健 2026-05-15】IPv6 ping不含"TTL="，用packets_received>0作为补充判定
            if "TTL=" in raw_output or "ttl=" in raw_output.lower() or (loss_match and int(loss_match.group(2)) > 0):
                is_reachable = True
        else:
            loss_match = re.search(r"(\d+)\s+packets transmitted.*?(\d+)\s+received.*?(\d+)%\s+packet loss", raw_output, re.DOTALL)
            if loss_match:
                packets_sent = int(loss_match.group(1))
                packets_received = int(loss_match.group(2))
                loss_rate = float(loss_match.group(3))
                packets_lost = packets_sent - packets_received
            
            latency_match = re.search(r"rtt min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)", raw_output)
            if latency_match:
                min_latency = float(latency_match.group(1))
                avg_latency = float(latency_match.group(2))
                max_latency = float(latency_match.group(3))
            
            if packets_received > 0:
                is_reachable = True
        
        if is_reachable:
            # 【修复 小健 2026-05-16】llm_data直接给原始输出，≤5K全给，不再正则解析后重组避免N/A丢失
            _raw_len = len(raw_output)
            if _raw_len <= 5000:
                _llm_ping = {"目标": host, "结果": raw_output.strip()}
            else:
                _llm_ping = {
                    "目标": host,
                    "发包/收包": f"{packets_sent}/{packets_received}",
                    "丢包率": f"{loss_rate}%",
                    "延迟(avg/min/max)": f"{avg_latency}ms / {min_latency}ms / {max_latency}ms" if avg_latency else "N/A",
                    "原始输出(截断)": raw_output[:3000].strip(),
                }
            return build_success(
                {
                    "host": host,
                    "packets_sent": packets_sent,
                    "packets_received": packets_received,
                    "packets_lost": packets_lost,
                    "loss_rate": loss_rate,
                    "min_latency": min_latency,
                    "avg_latency": avg_latency,
                    "max_latency": max_latency,
                    "is_reachable": True,
                },
                f"Ping测试成功：{host} 可达，平均延迟 {avg_latency if avg_latency else 'N/A'} ms",
                llm_data=_llm_ping,
            )
        else:
            # 【修复 小健 2026-05-16】不可达时也用raw_output给LLM
            _raw_len = len(raw_output)
            if _raw_len <= 5000:
                _llm_ping_fail = {"目标": host, "结果": raw_output.strip()}
            else:
                _llm_ping_fail = {"目标": host, "结果预览": raw_output[:3000].strip()}
            return build_success(
                {
                    "host": host,
                    "packets_sent": packets_sent,
                    "packets_received": 0,
                    "packets_lost": packets_sent,
                    "loss_rate": 100.0,
                    "min_latency": None,
                    "avg_latency": None,
                    "max_latency": None,
                    "is_reachable": False,
                },
                f"Ping测试失败：{host} 不可达",
                llm_data=_llm_ping_fail,
            )
    
    except Exception as e:
        logger.error(f"[ping] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"Ping测试异常: {str(e)}")


async def _port_check(
    host: str,
    port: int,
    timeout: int = 3,
) -> dict:
    """
    检查端口是否开放 - 小沈 2026-05-02
    
    使用socket连接测试端口是否开放。
    
    参数:
        host: 目标主机地址（域名或IP）
        port: 端口号（1-65535）
        timeout: 连接超时时间（秒）
    
    返回:
        {
            "code": "SUCCESS",
            "data": {
                "host": "目标主机",
                "port": 端口号,
                "is_open": 是否开放,
                "service": 服务名称（如果已知）,
            },
            "message": "描述信息"
        }
    """
    try:
        if not host or len(host.strip()) == 0:
            return build_error("ERR_NETWORK_INVALID_HOST", "目标主机地址不能为空")
        
        if port < 1 or port > 65535:
            return build_error("ERR_NETWORK_INVALID_PORT", f"端口号无效：{port}，必须在 1-65535 范围内")
        
        host = host.strip()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((host, port))
            
            if result == 0:
                is_open = True
                sock.close()
                
                service = well_known_ports.get(port, "Unknown")
                
                return build_success(
                    {
                        "host": host,
                        "port": port,
                        "is_open": True,
                        "service": service,
                    },
                    f"端口 {port} ({service}) 开放：{host}:{port}",
                    llm_data={"主机": host, "端口": port, "开放": True, "服务": service},
                )
            else:
                sock.close()
                
                return build_success(
                    {
                        "host": host,
                        "port": port,
                        "is_open": False,
                        "service": well_known_ports.get(port, "Unknown"),
                    },
                    f"端口 {port} 关闭：{host}:{port}，请检查服务是否启动或防火墙设置",
                    llm_data={"主机": host, "端口": port, "开放": False},
                )
        
        except socket.gaierror as e:
            return build_error(
                "ERR_NETWORK_DNS_ERROR",
                f"DNS解析失败：{host} ({str(e)})",
                data={
                    "host": host,
                    "port": port,
                    "is_open": False,
                    "service": None,
                },
            )
        except socket.timeout:
            return build_success(
                {
                    "host": host,
                    "port": port,
                    "is_open": False,
                    "service": well_known_ports.get(port, "Unknown"),
                },
                f"端口 {port} 连接超时：{host}:{port}",
            )
        except OSError as e:
            return build_error(
                "ERR_NETWORK_CONNECTION_ERROR",
                f"连接失败：{str(e)}",
                data={
                    "host": host,
                    "port": port,
                    "is_open": False,
                    "service": None,
                },
            )
    
    except Exception as e:
        logger.error(f"[port_check] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"端口检查异常: {str(e)}")


async def network_diagnose(
    host: str,
    mode: Literal["ping", "port"] = "ping",
    port: Optional[int] = None,
    count: int = 4,
    timeout: int = 5,
) -> dict:
    """网络连通性诊断 - 小沈 2026-05-17
    【2026-05-17 小沈】合并 ping + port_check

    Args:
        host: 目标主机地址（域名或IP）
        mode: 诊断模式。ping=ICMP可达性检测(主机级), port=TCP端口检测(服务级)
        port: 目标端口号（mode="port"时必填，mode="ping"时忽略）
        count: ping次数（mode="ping"时生效，默认4次）
        timeout: 超时秒数，默认5

    Returns:
        {code, data, message}
    """
    if mode == "ping":
        result = await _ping(host=host, count=count, timeout=timeout)
    elif mode == "port":
        if port is None:
            return build_error("ERR_MISSING_PARAM", "mode='port'时port参数必填")
        result = await _port_check(host=host, port=port, timeout=timeout)
    else:
        return build_error("ERR_INVALID_MODE", f"无效的诊断模式: {mode}，必须是 ping 或 port")

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("network_diagnose", "深入诊断", "需要切换ping/port模式进一步检测时")])
    return result
