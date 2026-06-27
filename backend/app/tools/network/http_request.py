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

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client
from app.tools.network.connectivity import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy
from app.tools.validate.timeout_validator import validate_timeout
from app.utils.json_utils import coerce_json, parse_json

_check_network = check_network

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


_MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB


def _parse_response_body(response: httpx.Response) -> Dict[str, Any]:
    """解析HTTP响应体 — 小欧 2026-06-22 — 小欧 2026-06-24 增加JSON大小限制"""
    content_type = response.headers.get("content-type", "")
    content_type_short = content_type.split(";")[0].strip() if content_type else "unknown"

    if "application/json" in content_type:
        if len(response.content) > _MAX_JSON_SIZE:
            body = {"_truncated": True, "_preview": response.text[:_MAX_JSON_SIZE]}
        else:
            try:
                body = response.json()
            except (json.JSONDecodeError, ValueError):
                body = response.text
    else:
        body = response.text

    body_json_len = 0
    if isinstance(body, (dict, list)):
        body_json_len = len(json.dumps(body, ensure_ascii=False))

    if isinstance(body, (dict, list)):
        llm_body = body
    else:
        llm_body = str(body)

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
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    proxy: Optional[str] = None,
    retry: int = 3,
) -> Dict[str, Any]:
    """发起HTTP请求 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化"""
    headers = coerce_json(headers)
    body = coerce_json(body)
    if retry < 0 or retry > 10:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_NETWORK_INVALID_PARAM, detail=f"重试次数必须在0-10之间,当前值:{retry}")
        return build_error(data={"error_detail": f"重试次数必须在0-10之间", "params": {"retry": retry}}, llm_data=llm_data)

    timeout_valid, timeout_err, _ = validate_timeout(timeout, "http_request")
    if not timeout_valid:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_INVALID_URL, detail=timeout_err)
        return build_error(data={"error_detail": timeout_err, "params": {"url": url}}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_INVALID_URL, detail=proxy_err)
        return build_error(data={"error_detail": proxy_err, "params": {"proxy": proxy}}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()

    try:
        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_INVALID_URL, detail=error_msg or "URL格式无效")
            return build_error(data={"error_detail": error_msg or "URL格式无效", "params": {"url": url}}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[http_request] {warning_msg}")

        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用", "params": {"url": url}}, llm_data=llm_data)

        request_headers = {}
        if headers:
            request_headers.update(headers)

        last_exception = None
        async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
            for attempt in range(retry + 1):
                try:
                    method_upper = method.upper()
                    request_kwargs = {"url": url, "headers": request_headers}
                    if body is not None:
                        request_kwargs["json"] = body

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
                        backoff = min(0.5 * (2 ** attempt), 10.0)
                        await asyncio.sleep(backoff)
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