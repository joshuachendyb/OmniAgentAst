# -*- coding: utf-8 -*-
"""
Network 工具函数模块 - 网络通信工具
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件:
1. *_tools.py: 函数实现(必须有详细注释)
2. *_schema.py: Pydantic 模型(输入参数定义)
3. *_register.py: 显式注册(description + examples + input_model)

包含:
- http_request: 发起HTTP请求
- download_file: 下载文件到本地
- fetch_webpage: 获取和处理网页内容
- search_web: 搜索网络获取最新信息
- ping: 执行ping测试(小沈 2026-05-02)
- port_check: 检查端口是否开放(小沈 2026-05-02)

返回格式:统一 {code, data, message} 格式
- code: SUCCESS 或 ERR_xxx 错误码
- data: 成功时返回数据,失败时为 None
- message: 描述信息

Author: 小沈 - 2026-04-29
"""

import os
import json
import re
from app.utils.common_patterns import HTML_TAG_PATTERN, SCRIPT_TAG_PATTERN, STYLE_TAG_PATTERN, MULTI_WHITESPACE_PATTERN
import platform
import subprocess
import socket
import asyncio
import base64
import time as _time_mod
from typing import Optional, Dict, Any, Literal, List, Tuple
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from app.utils.logger import logger
from app.utils.json_utils import parse_json, coerce_json

from app.tools.toolhelper.network_helper import (  # 小健 2026-05-18
    well_known_ports, _html_to_markdown, _decode_bing_redirect_url,
    _validate_url, _check_network,  # 小沈 2026-05-25 提升到模块级,消除3处函数内重复import
)
from app.tools.network.http_client_sdk import create_http_client, HTTPClient  # 小沈 2026-05-29
from app.utils.tool_result_formatter import truncate_data_for_frontend, make_json_safe  # 小沈 2026-05-20
from app.constants import (
    BROWSER_USER_AGENT,
    DEFAULT_MAX_DOC_CHARS,
    DEFAULT_MAX_OUTPUT_CHARS,
    ERR_INVALID_MODE,
    ERR_INVALID_URL,
    ERR_MISSING_PARAM,
    ERR_NETWORK_CONNECTION_ERROR,
    ERR_NETWORK_CREATE_DIR,
    ERR_NETWORK_DNS_ERROR,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_INVALID_HOST,
    ERR_NETWORK_INVALID_PARAM,
    ERR_NETWORK_INVALID_PATH,
    ERR_NETWORK_INVALID_PORT,
    ERR_NETWORK_JS_RENDER,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NETWORK_WRITE_FILE,
    ERR_NET_UNKNOWN,
    ERR_PARAM_INVALID,
    ERR_SHELL_COMMAND_NOT_FOUND,
    RETRYABLE_HTTP_STATUS_CODES,
)
from app.tools.tool_response import build_success, build_error
from app.constants import SUCCESS_CODE


# ========== builder函数 ==========

def _build_http_request_llm_data(exec_code: str, duration_ms: int, url: str = "", method: str = "GET",
                                   status_code: int = 0, content_type: str = "", llm_body=None,
                                   err_code: str = "", detail: str = "") -> dict:
    """http_request的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"HTTP请求失败: {method} {url}",
            "action": {"tool": "http_request", "tool_zh": "HTTP请求", "target": url, "params": {"method": method, "url": url}},
            "status": {"exec_code": "error", "message": "HTTP请求失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"请求成功 (HTTP {status_code})",
        "action": {"tool": "http_request", "tool_zh": "HTTP请求", "target": url, "params": {"method": method, "url": url}},
        "status": {"exec_code": "success", "message": "HTTP请求成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"status_code": {"value": status_code, "text": f"HTTP {status_code}"}},
    }


def _build_download_file_llm_data(exec_code: str, duration_ms: int, url: str = "", dest_path: str = "",
                                    file_size: int = 0, total_size: int = 0, content_type: str = "",
                                    err_code: str = "", detail: str = "") -> dict:
    """download_file的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"文件下载失败: {url}",
            "action": {"tool": "download_file", "tool_zh": "文件下载", "target": url, "params": {"url": url}},
            "status": {"exec_code": "error", "message": "文件下载失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"文件下载成功: {dest_path}",
        "action": {"tool": "download_file", "tool_zh": "文件下载", "target": url, "params": {"url": url, "destination_path": dest_path}},
        "status": {"exec_code": "success", "message": "文件下载成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"file_size": {"value": file_size, "text": f"{file_size}字节"}},
    }


def _build_fetch_webpage_llm_data(exec_code: str, duration_ms: int, url: str = "", extract_format: str = "markdown",
                                    status_code: int = 0, truncated: bool = False, content_preview: str = "",
                                    err_code: str = "", detail: str = "") -> dict:
    """fetch_webpage的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"获取网页失败: {url}",
            "action": {"tool": "fetch_webpage", "tool_zh": "获取网页", "target": url, "params": {"url": url, "extract_format": extract_format}},
            "status": {"exec_code": "error", "message": "获取网页失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"成功获取网页内容({extract_format}格式)" + ("(已截断)" if truncated else ""),
        "action": {"tool": "fetch_webpage", "tool_zh": "获取网页", "target": url, "params": {"url": url, "extract_format": extract_format}},
        "status": {"exec_code": "success", "message": "获取网页内容成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"status_code": {"value": status_code, "text": f"HTTP {status_code}"}},
    }


def _build_search_web_llm_data(exec_code: str, duration_ms: int, query: str = "", engine_used: str = "",
                                result_count: int = 0, llm_results=None,
                                err_code: str = "", detail: str = "") -> dict:
    """search_web的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"搜索失败: {query}",
            "action": {"tool": "search_web", "tool_zh": "网络搜索", "target": query, "params": {"query": query}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"找到 {result_count} 条搜索结果({engine_used})",
        "action": {"tool": "search_web", "tool_zh": "网络搜索", "target": query, "params": {"query": query}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"results": {"value": result_count, "text": f"{result_count}条"}},
    }


def _build_ping_llm_data(exec_code: str, duration_ms: int, host: str = "", is_reachable: bool = False,
                          packets_sent: int = 0, packets_received: int = 0, loss_rate: float = 0.0,
                          avg_latency=None, min_latency=None, max_latency=None,
                          err_code: str = "", detail: str = "") -> dict:
    """ping的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"Ping测试失败: {host}",
            "action": {"tool": "ping", "tool_zh": "Ping测试", "target": host, "params": {"host": host}},
            "status": {"exec_code": "error", "message": "Ping测试失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    status_text = "可达" if is_reachable else "不可达"
    metrics = {}
    if is_reachable:
        metrics["loss_rate"] = {"value": loss_rate, "text": f"{loss_rate}%"}
        if avg_latency is not None:
            metrics["avg_latency"] = {"value": avg_latency, "text": f"{avg_latency}ms"}
    return {
        "summary": f"Ping测试{'成功' if is_reachable else '失败'}:{host} {status_text}",
        "action": {"tool": "ping", "tool_zh": "Ping测试", "target": host, "params": {"host": host}},
        "status": {"exec_code": "success" if is_reachable else "error", "message": f"Ping {status_text}", "code": "" if is_reachable else ERR_NETWORK_TIMEOUT, "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def _build_port_check_llm_data(exec_code: str, duration_ms: int, host: str = "", port: int = 0,
                                is_open: bool = False, service: str = "",
                                err_code: str = "", detail: str = "") -> dict:
    """port_check的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"端口检查失败: {host}:{port}",
            "action": {"tool": "port_check", "tool_zh": "端口检查", "target": f"{host}:{port}", "params": {"host": host, "port": port}},
            "status": {"exec_code": "error", "message": "端口检查失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    status_text = "开放" if is_open else "关闭"
    return {
        "summary": f"端口 {port} ({service}) {status_text}: {host}:{port}",
        "action": {"tool": "port_check", "tool_zh": "端口检查", "target": f"{host}:{port}", "params": {"host": host, "port": port}},
        "status": {"exec_code": "success", "message": f"端口{status_text}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _parse_response_body(response: httpx.Response) -> Dict[str, Any]:
    """解析 HTTP 响应体并构建 llm_data。
    Returns: {"body": 前端数据, "llm_body": LLM 数据, "content_type_short": str}
    """
    content_type = response.headers.get("content-type", "")
    content_type_short = content_type.split(";")[0].strip() if content_type else "unknown"

    if "application/json" in content_type:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            body = response.text
    else:
        body = response.text

    body_json_len = 0
    if isinstance(body, (dict, list)):
        body_json_len = len(json.dumps(body, ensure_ascii=False))

    if isinstance(body, str) and len(body) > 5000:
        if not parse_json(body):
            body = body[:4000] + f"\n...[截断 {len(body)-4000} 字符]"

    if isinstance(body, (dict, list)) and body_json_len <= 5000:
        llm_body = body
    elif isinstance(body, str) and len(body) <= 5000:
        llm_body = body
    elif isinstance(body, (dict, list)):
        from app.utils.tool_result_formatter import make_json_safe
        llm_body = make_json_safe(body, max_depth=4, max_str_len=500)
    else:
        llm_body = str(body)[:4000]

    return {
        "body": truncate_data_for_frontend({
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
        }),
        "llm_body": llm_body,
        "content_type_short": content_type_short,
    }


def _build_http_error(last_exception: Exception, url: str, retry: int, duration_ms: int = 0) -> Dict[str, Any]:
    """构建HTTP请求最终错误响应 — 小健 2026-06-21 builder改造"""
    if isinstance(last_exception, httpx.TimeoutException):
        llm_data = _build_http_request_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_TIMEOUT, detail="请求超时")
        return build_error(data={"url": url}, llm_data=llm_data)
    if isinstance(last_exception, httpx.HTTPStatusError):
        llm_data = _build_http_request_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_HTTP_ERROR,
                                                  detail=f"HTTP {last_exception.response.status_code}")
        return build_error(
            data={
                "status_code": last_exception.response.status_code,
                "body": last_exception.response.text if hasattr(last_exception.response, 'text') else None,
            }, llm_data=llm_data)
    llm_data = _build_http_request_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_REQUEST_ERROR, detail=str(last_exception))
    return build_error(data={"url": url, "error": str(last_exception), "retry": retry}, llm_data=llm_data)


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
    """发起HTTP请求 — 小健 2026-06-21 builder改造"""
    headers = coerce_json(headers)
    params = coerce_json(params)
    json_body = coerce_json(json_body)
    if retry < 0 or retry > 10:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_NETWORK_INVALID_PARAM, detail=f"重试次数必须在0-10之间,当前值:{retry}")
        return build_error(data={"retry": retry}, llm_data=llm_data)
    
    timeout_sec = timeout / 1000.0
    t0 = _time_mod.perf_counter()
    
    try:
        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_INVALID_URL, detail="URL格式无效")
            return build_error(data={"url": url}, llm_data=llm_data)

        net_info = _check_network()
        if not net_info["data"]["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用"}, llm_data=llm_data)

        parsed_url = urlparse(url)
        if params:
            query_string = urlencode(params, doseq=True)
            url = urlunparse(parsed_url._replace(query=query_string))

        request_headers = {}
        if headers:
            request_headers.update(headers)

        last_exception = None
        for attempt in range(retry + 1):
            try:
                async with create_http_client(timeout_sec=timeout_sec, proxy=proxy) as client:
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

                    parsed = _parse_response_body(response)
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    data = parsed["body"]
                    llm_data = _build_http_request_llm_data("success", duration_ms, url, method,
                                                            response.status_code, parsed["content_type_short"])
                    return build_success(data=data, llm_data=llm_data)
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exception = e
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in RETRYABLE_HTTP_STATUS_CODES:
                    try:
                        error_body = e.response.text
                    except Exception:
                        error_body = None
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                              err_code=ERR_NETWORK_HTTP_ERROR,
                                                              detail=f"HTTP {e.response.status_code}")
                    return build_error(
                        data={"status_code": e.response.status_code, "body": error_body}, llm_data=llm_data)
                if attempt < retry:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                break

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return _build_http_error(last_exception, url, retry, duration_ms)

    except Exception as e:
        logger.error(f"[http_request] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


NET_ERROR_MAP = [
    (httpx.TimeoutException, ERR_NETWORK_TIMEOUT, "下载超时"),
    (httpx.HTTPStatusError, ERR_NETWORK_HTTP_ERROR, "下载失败"),
    (httpx.RequestError, ERR_NETWORK_REQUEST_ERROR, "网络请求失败"),
]


def _map_network_error(url: str, timeout: int, e: Exception, duration_ms: int = 0) -> Dict[str, Any]:
    """将 httpx 异常映射为 build_error — 小健 2026-06-21 builder改造"""
    for exc_type, code, prefix in NET_ERROR_MAP:
        if isinstance(e, exc_type):
            detail = f"{prefix}({timeout/1000}秒):{url}"
            if isinstance(e, httpx.HTTPStatusError):
                detail = f"{prefix} (HTTP {e.response.status_code}):{url}"
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=code, detail=detail)
            return build_error(data={"url": url, "error": str(e)}, llm_data=llm_data)
    logger.error(f"[download_file] 未知错误: {e}")
    llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NET_UNKNOWN, detail=str(e))
    return build_error(data={"error": str(e)}, llm_data=llm_data)


async def _stream_download(client: HTTPClient, url: str, dest_path: str,
                           headers: dict, chunk_size: int = 8192) -> Tuple[int, str, int]:
    """流式下载文件到本地,返回 (downloaded_bytes, content_type, total_bytes) — 小健 2026-05-25"""
    async with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        total_bytes = int(response.headers.get("content-length", 0))

        downloaded = 0
        try:
            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
        except (PermissionError, OSError):
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise
        return downloaded, content_type, total_bytes


async def download_file(
    url: str,
    destination_path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 300000,
    proxy: Optional[str] = None,
) -> dict:
    """从URL下载文件 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_INVALID_URL, detail="URL格式无效")
            return build_error(data={"url": url}, llm_data=llm_data)
        net_info = _check_network()
        if not net_info["data"]["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用"}, llm_data=llm_data)

        dest_path = os.path.abspath(destination_path)
        dest_dir = os.path.dirname(dest_path)
        if not dest_dir:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_INVALID_PATH, detail=f"无效路径: {destination_path}")
            return build_error(data={"path": destination_path}, llm_data=llm_data)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_CREATE_DIR, detail=str(e))
            return build_error(data={"error_detail": str(e)}, llm_data=llm_data)

        req_headers = headers or {}

        async with create_http_client(timeout_sec=timeout / 1000.0, proxy=proxy) as client:
            downloaded, content_type, total_bytes = await _stream_download(client, url, dest_path, req_headers)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"file_path": dest_path, "file_size": downloaded, "total_size": total_bytes, "content_type": content_type}
        llm_data = _build_download_file_llm_data("success", duration_ms, url, dest_path, downloaded, total_bytes, content_type)
        return build_success(data=data, llm_data=llm_data)
    except (PermissionError, OSError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_NETWORK_WRITE_FILE, detail=str(e))
        return build_error(data={"file_path": dest_path, "error_detail": str(e)}, llm_data=llm_data)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return _map_network_error(url, timeout, e, duration_ms)
    except Exception as e:
        logger.error(f"[download_file] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _extract_html_content(html_content: str, extract_format: str, max_tokens: int) -> Tuple[str, bool]:
    """3路格式提取+截断检查。消除A/B路径完全重复代码 — 小健 2026-05-25"""
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


def _build_media_result(url: str, mime: str, raw_bytes: bytes, extract_format: str, response_status: int) -> Dict:
    """构建图片/PDF的base64附件响应 — 小健 2026-06-21 builder改造"""
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data = {
        "url": url,
        "content": f"[{mime} 文件,大小: {len(raw_bytes)} 字节]",
        "format": extract_format,
        "content_type": mime,
        "status_code": response_status,
        "truncated": False,
    }
    llm_data = _build_fetch_webpage_llm_data("success", 0, url, extract_format, response_status)
    other_data = {
        "attachment": {
            "type": "base64",
            "mime": mime,
            "data": b64,
            "filename": url.split("/")[-1].split("?")[0] or "download",
        }
    }
    return build_success(data=data, llm_data=llm_data, other_data=other_data)


async def _fetch_via_playwright(url: str, proxy: Optional[str], timeout_sec: float,
                                extract_format: str, max_tokens: int) -> Dict:
    """Playwright路径封装 — 小健 2026-06-21 builder改造"""
    try:
        from playwright.async_api import async_playwright

    except ImportError:
        llm_data = _build_fetch_webpage_llm_data("error", 0, url, extract_format, err_code=ERR_NETWORK_JS_RENDER, detail="js_render需要安装Playwright")
        return build_error(data={"error_detail": "js_render需要安装Playwright: pip install playwright && playwright install chromium"}, llm_data=llm_data)
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
        llm_data = _build_fetch_webpage_llm_data("error", 0, url, extract_format, err_code=ERR_NETWORK_JS_RENDER, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


async def fetch_webpage(
    url: str,
    prompt: Optional[str] = None,
    extract_format: str = "markdown",
    js_render: bool = False,
    timeout: int = 30000,
    proxy: Optional[str] = None,
) -> dict:
    """获取网页内容 — 小健 2026-06-21 builder改造"""
    max_tokens = 8000
    timeout_sec = timeout / 1000.0
    t0 = _time_mod.perf_counter()

    try:
        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_INVALID_URL, detail="URL格式无效")
            return build_error(data={"url": url}, llm_data=llm_data)

        net_info = _check_network()
        if not net_info["data"]["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用"}, llm_data=llm_data)

        headers = {
            "User-Agent": BROWSER_USER_AGENT,
        }
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        headers["Accept-Language"] = "en-US,en;q=0.9,zh-CN;q=0.8"
        headers["Accept-Encoding"] = "gzip, deflate"

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
                    return _build_media_result(url, mime, raw_bytes, extract_format, response.status_code)

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
        return build_error(data={"url": url, "timeout": timeout_sec}, llm_data=llm_data)
    except httpx.HTTPStatusError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_HTTP_ERROR, detail=f"HTTP {e.response.status_code}")
        return build_error(data={"url": url, "status_code": e.response.status_code}, llm_data=llm_data)
    except httpx.RequestError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_REQUEST_ERROR, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[fetch_webpage] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)




# 【24.2.4 组件1】MCP_CONFIGS 提至模块级常量 — 每次调用避免重建
_MCP_CONFIGS = {
    "parallel": {
        "url": "https://search.parallel.ai/mcp",
        "tool_name": "web_search",
        "build_args": lambda q, n: {"objective": q, "search_queries": [q], "session_id": "omniagent-search"},
    },
    "exa": {
        "url": "https://mcp.exa.ai/mcp",
        "tool_name": "web_search_exa",
        "build_args": lambda q, n: {"query": q, "type": "auto", "numResults": n, "livecrawl": "fallback"},
    },
}


# 【24.2.4 组件2】统一失败日志 + return None(消除 7 路重复)
def _search_failed(engine: str, reason: str = "") -> None:
    """日志记录 MCP 搜索失败 — 小健 2026-05-25"""
    logger.info(f"[_search_mcp_engine:{engine}] {reason}" if reason else f"[_search_mcp_engine:{engine}] 失败")


# 【24.2.4 组件3】从 P1c 提取为独立函数(消除 R1b 无结果 + 逐行状态机)
def _parse_exa_results(text: str, num_results: int) -> Optional[List[Dict[str, str]]]:
    """解析 Exa MCP 的文本格式结果 — 小健 2026-05-25"""
    results = []
    current = {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Title: "):
            if current.get("title"):
                results.append(current)
                if len(results) >= num_results:
                    break
            current = {"title": line[7:], "url": "", "snippet": ""}
        elif line.startswith("URL: "):
            current["url"] = line[5:]
        elif line.startswith("Highlights:") or (current.get("snippet") == "" and line and
              not line.startswith("Published") and not line.startswith("Author")):
            if not current["snippet"]:
                current["snippet"] = line[:300]
    if current.get("title"):
        results.append(current)

    formatted = [
        {"title": r["title"], "url": r["url"], "snippet": r.get("snippet", "")[:300], "source": "Exa"}
        for r in results[:num_results] if r.get("title") and r.get("url")
    ]
    return formatted or None


async def _search_mcp_engine(engine: str, query: str, num_results: int, proxy: Optional[str] = None) -> Optional[List[dict]]:
    """MCP搜索引擎统一入口 - 小沈 2026-05-17
    合并 _search_parallel_mcp + _search_exa_mcp,消除约80行重复代码。
    
    Args:
        engine: "parallel" | "exa"
        query: 搜索关键词
        num_results: 结果数量
        proxy: 代理服务器地址(小沈 2026-05-19 修复:新增proxy参数)
    
    Returns:
        搜索结果列表或None(失败时)
    """
    config = _MCP_CONFIGS.get(engine)
    if not config:
        _search_failed(engine, "未知引擎")
        return None

    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": config["tool_name"], "arguments": config["build_args"](query, num_results)},
    }
    try:
        async with create_http_client(timeout_sec=25.0, proxy=proxy) as client:
            resp = await client.post(config["url"], json=payload,
                headers={"Accept": "application/json, text/event-stream"})
            resp.raise_for_status()
            data = resp.json()
            result_text = data.get("result", {}).get("content", [{}])[0].get("text", "")
            if not result_text:
                _search_failed(engine, "返回空数据")
                return None

        if engine == "parallel":
            if not result_text.startswith("{"):
                _search_failed(engine, "返回数据非JSON")
                return None
            parsed = parse_json(result_text, raise_on_error=True)
            results = []
            for r in parsed.get("results", [])[:num_results]:
                title, url = r.get("title", ""), r.get("url", "")
                if title and url:
                    snippet = (r.get("excerpts", [])[0] or "")[:300]
                    results.append({"title": title, "url": url, "snippet": snippet, "source": "Parallel"})
            if not results:
                _search_failed(engine, "无搜索结果")
                return None
            return results
        else:  # exa
            formatted = _parse_exa_results(result_text, num_results)
            if not formatted:
                _search_failed(engine, "无搜索结果")
            return formatted

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
        _search_failed(engine, f"网络错误: {type(e).__name__}")
    except Exception as e:
        _search_failed(engine, f"异常: {type(e).__name__}")
    return None  # 所有异常汇聚到唯一 return None


async def search_web(
    query: str,
    allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None,
    num_results: int = 10,
    proxy: Optional[str] = None,
) -> dict:
    """搜索网络 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if len(query) < 2:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_PARAM_INVALID, detail="搜索查询至少需要2个字符")
            return build_error(data={"error_detail": "搜索查询至少需要2个字符"}, llm_data=llm_data)
        
    # ===== 第一引擎:Parallel MCP =====
        results = await _search_mcp_engine("parallel", query, num_results, proxy)
        engine_used = "Parallel"
        
        # ===== 第二引擎:Exa MCP =====
        if results is None:
            logger.info("[search_web] Parallel失败,降级到Exa MCP搜索")
            results = await _search_mcp_engine("exa", query, num_results, proxy)
            engine_used = "Exa"
        
        # ===== 第三引擎:Bing中国 =====
        if results is None:
            logger.info("[search_web] Exa失败,降级到Bing中国搜索")
            try:
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

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"query": query, "results": results, "total": len(results), "engine": engine_used}
        llm_data = _build_search_web_llm_data("success", duration_ms, query, engine_used, len(results))
        return build_success(data=data, llm_data=llm_data)
    
    except Exception as e:
        logger.error(f"[search_web] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


async def _search_bing(
    query: str,
    num_results: int,
    proxy_config: Optional[str] = None,
) -> List[dict]:
    """Bing搜索(HTML解析)- 小沈 2026-05-07, 小健 2026-05-19 proxy_config改字符串
    国内可访问,无需API Key,解析搜索结果页HTML
    """
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
    }
    params = {"q": query, "count": num_results}
    
    async with create_http_client(timeout_sec=15.0, proxy=proxy_config) as client:
        response = await client.get("https://cn.bing.com/search", params=params, headers=headers)
        response.raise_for_status()
        html = response.text
    
    results = []
    # Bing搜索结果在 <li class="b_algo"> 块中
    # URL在 <a href="..."> 中,标题在 <h2> 中,摘要在 <p> 或 <div class="b_caption"><p> 中
    algo_blocks = re.split(r'<li\s+class="b_algo"', html)
    for block in algo_blocks[1:]:
        if len(results) >= num_results:
            break
        # 提取URL:优先找非bing.com的外部链接,其次是bing.com/ck/a跳转链接
        a_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', block[:3000])
        if not a_match:
            continue
        url = a_match.group(1)
        # 【2026-05-13 小沈】Bing现在所有结果都用ck/a跳转链接,没有直接外部URL
        # HTTP跟随跳转会返回原URL(无法解码),所以直接保留ck/a链接作为结果
        if "bing.com/ck/a" in url:
            # 保留跳转链接,用户点击后会被重定向到真实网站
            pass
        elif "bing.com" in url or "microsoft.com" in url:
            continue
        
        # 提取标题:优先从<h2>取(Bing的真实标题在h2中)
        h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block[:3000], re.DOTALL)
        if h2_match:
            title = HTML_TAG_PATTERN.sub('', h2_match.group(1)).strip()
        else:
            # 兜底从<a>取
            a_text_match = re.search(r'<a[^>]+href="[^"]+ "[^>]*>(.*?)</a>', block[:3000], re.DOTALL)
            title = HTML_TAG_PATTERN.sub('', a_text_match.group(1)).strip() if a_text_match else ""
        # 提取摘要
        snippet = ""
        p_match = re.search(r'<div\s+class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
        if not p_match:
            p_match = re.search(r'<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
        if p_match:
            snippet = HTML_TAG_PATTERN.sub('', p_match.group(1)).strip()
            snippet = re.sub(r'&ensp;|&#\d+;', ' ', snippet).strip()
        
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet, "source": "Bing"})
    
    if not results:
        logger.warning("[_search_bing] 主解析未提取到结果,尝试简易模式")
        href_pattern = re.compile(r'<a\s+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        for match in href_pattern.finditer(html):
            url = match.group(1)
            title = HTML_TAG_PATTERN.sub('', match.group(2)).strip()
            if "bing.com/ck/a" in url:
                pass  # 保留跳转链接
            elif "bing.com" in url or "microsoft.com" in url:
                continue
            if title and len(title) > 5:
                results.append({"title": title, "url": url, "snippet": "", "source": "Bing"})
            if len(results) >= num_results:
                break
    
    return results



def _build_ping_cmd(host: str, count: int, timeout: int) -> List[str]:
    """根据平台构建ping命令 — 小沈 2026-05-25 重构"""
    system = platform.system().lower()
    if system == "windows":
        return ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    return ["ping", "-c", str(count), "-W", str(timeout), host]


def _parse_ping_output(raw_output: str, system: str) -> dict:
    """解析ping输出,返回 {sent, received, lost, loss%, min, avg, max, reachable} — 小沈 2026-05-25 重构"""
    result = {"packets_sent": 0, "packets_received": 0, "packets_lost": 0, "loss_rate": 0.0,
              "min_latency": None, "avg_latency": None, "max_latency": None, "is_reachable": False}
    if system == "windows":
        loss = re.search(r"(?:已发送|Sent\s*=\s*)(\d+).*?(?:已接收|Received\s*=\s*)(\d+).*?(?:丢失|Lost\s*=\s*)(\d+).*?(\d+)%", raw_output, re.DOTALL | re.IGNORECASE)
        if loss:
            result.update(packets_sent=int(loss.group(1)), packets_received=int(loss.group(2)),
                          packets_lost=int(loss.group(3)), loss_rate=float(loss.group(4)))
        latency = re.search(r"(?:最短|Minimum)\s*[=:]\s*([\d.]+).*?(?:最长|Maximum)\s*[=:]\s*([\d.]+).*?(?:平均|Average)\s*[=:]\s*([\d.]+)", raw_output, re.DOTALL | re.IGNORECASE)
        if latency:
            result.update(min_latency=float(latency.group(1)), max_latency=float(latency.group(2)),
                          avg_latency=float(latency.group(3)))
        if "TTL=" in raw_output.upper() or (loss and int(loss.group(2)) > 0):
            result["is_reachable"] = True
    else:
        loss = re.search(r"(\d+)\s+packets transmitted.*?(\d+)\s+received.*?(\d+)%\s+packet loss", raw_output, re.DOTALL)
        if loss:
            sent, recv, rate = int(loss.group(1)), int(loss.group(2)), float(loss.group(3))
            result.update(packets_sent=sent, packets_received=recv, packets_lost=sent-recv, loss_rate=rate)
        latency = re.search(r"rtt min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)", raw_output)
        if latency:
            result.update(min_latency=float(latency.group(1)), avg_latency=float(latency.group(2)),
                          max_latency=float(latency.group(3)))
        if result["packets_received"] > 0:
            result["is_reachable"] = True
    return result


def _build_ping_result(host: str, raw_output: str, parsed: dict, duration_ms: int = 0) -> dict:
    """统一构建ping的build_success响应 — 小健 2026-06-21 builder改造"""
    data = {"host": host, **parsed}
    reachable = parsed["is_reachable"]

    if not reachable:
        data.update(packets_received=0, packets_lost=parsed["packets_sent"],
                     loss_rate=100.0, min_latency=None, avg_latency=None, max_latency=None)

    llm_data = _build_ping_llm_data("success" if reachable else "error", duration_ms, host, reachable,
                                      parsed.get("packets_sent", 0), parsed.get("packets_received", 0),
                                      parsed.get("loss_rate", 0.0), parsed.get("avg_latency"),
                                      parsed.get("min_latency"), parsed.get("max_latency"))
    return build_success(data=data, llm_data=llm_data)


async def _ping(host: str, count: int = 4, timeout: int = 5) -> dict:
    """Ping测试(内部函数) — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if not host or not host.strip():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_ping_llm_data("error", duration_ms, host, err_code=ERR_NETWORK_INVALID_HOST, detail="目标主机地址不能为空")
            return build_error(data={"error_detail": "目标主机地址不能为空"}, llm_data=llm_data)
        host = host.strip()
        cmd = _build_ping_cmd(host, count, timeout)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=count * timeout + 10)
            raw_output = result.stdout
        except subprocess.TimeoutExpired:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_ping_llm_data("error", duration_ms, host, err_code=ERR_NETWORK_TIMEOUT, detail=f"Ping超时({count * timeout + 10}秒)")
            return build_error(data={"host": host, "timeout": count * timeout + 10}, llm_data=llm_data)
        except FileNotFoundError:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_ping_llm_data("error", duration_ms, host, err_code=ERR_SHELL_COMMAND_NOT_FOUND, detail="系统ping命令不可用")
            return build_error(data={"error_detail": "系统ping命令不可用"}, llm_data=llm_data)

        parsed = _parse_ping_output(raw_output, platform.system().lower())
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return _build_ping_result(host, raw_output, parsed, duration_ms)

    except Exception as e:
        logger.error(f"[ping] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_ping_llm_data("error", duration_ms, host, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"host": host, "error_detail": str(e)}, llm_data=llm_data)


# 【24.5.4 组件1】统一端口结果 data 构建(消除 5 次 data dict)
def _build_port_result(host: str, port: int, is_open: bool,
                        service: Optional[str] = None) -> Dict[str, Any]:
    """构建端口检查结果 data — 小健 2026-05-25"""
    return {"host": host, "port": port, "is_open": is_open, "service": service}


async def _port_check(
    host: str,
    port: int,
    timeout: int = 3,
) -> dict:
    """检查端口是否开放 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if not host or not host.strip():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_INVALID_HOST, detail="目标主机地址不能为空")
            return build_error(data={"error_detail": "目标主机地址不能为空"}, llm_data=llm_data)
        if port < 1 or port > 65535:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_INVALID_PORT, detail=f"端口号无效: {port}")
            return build_error(data={"port": port}, llm_data=llm_data)
        host = host.strip()
        service = well_known_ports.get(port, "Unknown")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            is_open = sock.connect_ex((host, port)) == 0
        finally:
            sock.close()

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = _build_port_result(host, port, is_open, service)
        llm_data = _build_port_check_llm_data("success", duration_ms, host, port, is_open, service)
        return build_success(data=data, llm_data=llm_data)

    except socket.gaierror as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_DNS_ERROR, detail=f"DNS解析失败: {host}")
        return build_error(data=_build_port_result(host, port, False), llm_data=llm_data)
    except socket.timeout:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_port_check_llm_data("error", duration_ms, host, port, service=service, err_code=ERR_NETWORK_TIMEOUT, detail=f"端口 {port} 连接超时")
        return build_error(data=_build_port_result(host, port, False, service), llm_data=llm_data)
    except OSError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_CONNECTION_ERROR, detail=str(e))
        return build_error(data=_build_port_result(host, port, False), llm_data=llm_data)
    except Exception as e:
        logger.error(f"[port_check] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"host": host, "port": port, "error_detail": str(e)}, llm_data=llm_data)


async def network_diagnose(
    host: str,
    mode: Literal["ping", "port"] = "ping",
    port: Optional[int] = None,
    count: int = 4,
    timeout: int = 5,
) -> dict:
    """网络连通性诊断 — 小健 2026-06-21 builder改造"""
    if mode == "ping":
        result = await _ping(host=host, count=count, timeout=timeout)
    elif mode == "port":
        if port is None:
            return build_error(data={"error_detail": "mode='port'时port参数必填"}, llm_data={
                "summary": "网络诊断失败: 缺少port参数", "action": {"tool": "network_diagnose", "tool_zh": "网络诊断", "target": host, "params": {"mode": mode}},
                "status": {"exec_code": "error", "message": "缺少port参数", "code": ERR_MISSING_PARAM, "detail": "", "hint": ""},
                "duration_ms": 0, "metrics": {}})
        result = await _port_check(host=host, port=port, timeout=timeout)
    else:
        return build_error(data={"error_detail": f"无效的诊断模式: {mode}", "mode": mode}, llm_data={
            "summary": f"网络诊断失败: 无效模式 {mode}", "action": {"tool": "network_diagnose", "tool_zh": "网络诊断", "target": host, "params": {"mode": mode}},
            "status": {"exec_code": "error", "message": "无效的诊断模式", "code": ERR_INVALID_MODE, "detail": "", "hint": ""},
            "duration_ms": 0, "metrics": {}})

    return result
