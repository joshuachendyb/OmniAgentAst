# -*- coding: utf-8 -*-
"""
N1: http_request — 发起HTTP请求

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _parse_response_body / _build_http_error 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import asyncio
import json
import time as _time_mod
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

import socket
import time
from urllib.parse import urlparse

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client
from app.utils.json_utils import coerce_json
from app.utils.tool_result_formatter import make_json_safe
from app.utils.logger import logger
from app.constants import (
    ERR_INVALID_URL,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_INVALID_PARAM,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NET_UNKNOWN,
    RETRYABLE_HTTP_STATUS_CODES,
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


def _build_http_request_llm_data(
    exec_code: str, duration_ms: int, url: str = "", method: str = "GET",
    status_code: int = 0, content_type: str = "", llm_body=None,
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """http_request的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"HTTP请求失败: {method} {url}",
            "action": {"tool": "http_request", "tool_zh": "HTTP请求", "target": url, "params": {"method": method, "url": url}},
            "status": {"exec_code": "error", "message": "HTTP请求失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"请求成功 (HTTP {status_code})",
        "action": {"tool": "http_request", "tool_zh": "HTTP请求", "target": url, "params": {"method": method, "url": url}},
        "status": {"exec_code": "success", "message": "HTTP请求成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"status_code": {"value": status_code, "text": f"HTTP {status_code}"}},
    }


def _parse_response_body(response: httpx.Response) -> Dict[str, Any]:
    """解析HTTP响应体 — 小欧 2026-06-22"""
    from app.utils.json_utils import parse_json

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
        llm_body = make_json_safe(body, max_depth=4, max_str_len=500)
    else:
        llm_body = str(body)[:4000]

    return {
        "body": {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
        },
        "llm_body": llm_body,
        "content_type_short": content_type_short,
    }


def _build_http_error(last_exception: Exception, url: str, retry: int, duration_ms: int = 0) -> Dict[str, Any]:
    """构建HTTP请求最终错误信息字典 — 小欧 2026-06-22"""
    if isinstance(last_exception, httpx.TimeoutException):
        return {"error_detail": "请求超时", "params": {"url": url}, "err_code": ERR_NETWORK_TIMEOUT, "detail": "请求超时"}
    if isinstance(last_exception, httpx.HTTPStatusError):
        return {"error_detail": f"HTTP {last_exception.response.status_code}", "params": {"url": url, "status_code": last_exception.response.status_code}, "err_code": ERR_NETWORK_HTTP_ERROR, "detail": f"HTTP {last_exception.response.status_code}"}
    return {"error_detail": str(last_exception), "params": {"url": url, "retry": retry}, "err_code": ERR_NETWORK_REQUEST_ERROR, "detail": str(last_exception)}


async def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 30000,
    proxy: Optional[str] = None,
    retry: int = 3,
) -> Dict[str, Any]:
    """发起HTTP请求 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    headers = coerce_json(headers)
    params = coerce_json(params)
    json_body = coerce_json(json_body)
    if retry < 0 or retry > 10:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_NETWORK_INVALID_PARAM, detail=f"重试次数必须在0-10之间,当前值:{retry}")
        return build_error(data={"error_detail": f"重试次数必须在0-10之间", "params": {"retry": retry}}, llm_data=llm_data)

    timeout_sec = timeout / 1000.0
    t0 = _time_mod.perf_counter()

    try:
        url_info = _validate_url(url)
        if not url_info["valid"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_INVALID_URL, detail="URL格式无效")
            return build_error(data={"error_detail": "URL格式无效", "params": {"url": url}}, llm_data=llm_data)

        net_info = _check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用", "params": {"url": url}}, llm_data=llm_data)

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
                    request_kwargs = {"url": url, "headers": request_headers}
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
                        data={"error_detail": f"HTTP {e.response.status_code}", "params": {"url": url, "status_code": e.response.status_code, "body": error_body}},
                        llm_data=llm_data)
                if attempt < retry:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                break

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _build_http_error(last_exception, url, retry, duration_ms)
        llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=error_info["err_code"], detail=error_info["detail"])
        return build_error(data={"error_detail": error_info["error_detail"], "params": error_info["params"]}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"[http_request] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)