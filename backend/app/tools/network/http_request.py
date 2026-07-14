# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - #3 http请求异常详情丢失修复为类型:repr兜底
"""
N1: httpget — 发起HTTP请求

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _parse_response_body / _build_http_error 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import json
import time as _time_mod
from typing import Any, Dict, Optional

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client
from app.tools.network.network_register import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy
from app.tools.validate.timeout_validator import validate_timeout
from app.utils.json_utils import coerce_json
from app.logger import logger
from app.tools.tool_constants import (
    ERR_INVALID_URL,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_INVALID_PARAM,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
)

from app.tools.tool_constants import TOOL_RETRYABLE_HTTP_CODES


def _build_http_request_llm_data(
    exec_code: str, duration_ms: int, url: str = "", method: str = "GET",
    status_code: int = 0, content_type: str = "",
    err_code: str = "", detail: str = "", hint: str = "",
    timeout: int = 30, proxy: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None, body: Any = None,
) -> Dict[str, Any]:
    """http_request的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 过滤None值 — 小欧 2026-07-06 去掉headers/body，防止大字段返回给LLM"""
    _act_params = {"method": method, "url": url, "timeout": timeout}
    if proxy is not None:
        _act_params["proxy"] = proxy
    if exec_code == "error":
        return {
            "summary": f"HTTP请求:{url}，方法: {method} 失败",
            "action": {"tool": "httpget", "tool_zh": "HTTP请求", "target": url, "params": _act_params},
            "status": {"exec_code": "error", "message": "HTTP请求失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查URL和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    ctype_label = f" [{content_type}]" if content_type else ""
    return {
        "summary": f"HTTP请求:{url}成功: (HTTP {status_code}) ({ctype_label})",
        "action": {"tool": "httpget", "tool_zh": "HTTP请求", "target": url, "params": _act_params},
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
    """构建HTTP请求最终错误信息字典 — 小欧 2026-06-22 — 小欧 2026-07-08 空消息fallback"""
    if isinstance(last_exception, httpx.TimeoutException):
        return {"error_detail": "请求超时", "params": {"url": url}, "err_code": ERR_NETWORK_TIMEOUT, "detail": "请求超时"}
    if isinstance(last_exception, httpx.HTTPStatusError):
        return {"error_detail": f"HTTP {last_exception.response.status_code}", "params": {"url": url, "status_code": last_exception.response.status_code}, "err_code": ERR_NETWORK_HTTP_ERROR, "detail": f"HTTP {last_exception.response.status_code}"}
    _msg = f"{type(last_exception).__name__}: {str(last_exception) or repr(last_exception)}"  # — 小欧 2026-07-13
    return {"error_detail": _msg, "params": {"url": url, "retry": retry}, "err_code": ERR_NETWORK_REQUEST_ERROR, "detail": _msg}


async def httpget(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """发起HTTP请求 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化
    【小欧 2026-06-29】取消内建重试，异常传播给 ToolRetryEngine"""
    headers = coerce_json(headers)
    body = coerce_json(body)

    timeout_valid, timeout_err, _ = validate_timeout(timeout, "httpget")
    if not timeout_valid:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_NETWORK_INVALID_PARAM, detail=timeout_err, hint="请检查超时设置", timeout=timeout, proxy=proxy, headers=headers, body=body)
        return build_error(data={}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_http_request_llm_data("error", 0, url, method, err_code=ERR_NETWORK_INVALID_PARAM, detail=proxy_err, hint="请检查代理配置", timeout=timeout, proxy=proxy, headers=headers, body=body)
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()

    try:
        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_INVALID_URL, detail=error_msg or "URL格式无效", hint="请检查URL格式", timeout=timeout, proxy=proxy, headers=headers, body=body)
            return build_error(data={}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[httpget] {warning_msg}")

        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=ERR_NETWORK_DOWN, detail="网络不可用", hint="请检查网络连接", timeout=timeout, proxy=proxy, headers=headers, body=body)
            return build_error(data={}, llm_data=llm_data)

        request_headers = {}
        if headers:
            request_headers.update(headers)

        async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
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
                                                        response.status_code, parsed["content_type_short"],
                                                        timeout=timeout, proxy=proxy, headers=headers, body=body)
                # ---- observation_formatter route -------------------------------------------
                # branch: #19 httpget(body+headers)
                # trigger: "status_code" in data — data 含 status_code/headers/body
                # handler: _format_httpget_result(data)
                # file:    observation_formatter.py:197-198
                # ------------------------------------------------------------------------------
                return build_success(data=data, llm_data=llm_data)
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in TOOL_RETRYABLE_HTTP_CODES:
                    try:
                        error_body = e.response.text
                    except Exception:
                        error_body = None
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                              err_code=ERR_NETWORK_HTTP_ERROR,
                                                              detail=f"HTTP {e.response.status_code}",
                                                              hint="请检查URL和服务器状态",
                                                              timeout=timeout, proxy=proxy, headers=headers, body=body)
                    return build_error(
                        data={"error_detail": f"HTTP {e.response.status_code}", "params": {"url": url, "status_code": e.response.status_code}},
                        llm_data=llm_data)
                # 可重试异常 → 传播给 ToolRetryEngine
                raise

    except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e) or repr(e)}"  # — 小欧 2026-07-13
        logger.error(f"[httpget] 未知错误: {err_msg}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _build_http_error(e, url, 0, duration_ms)
        _hint = "可增大timeout参数重试" if error_info["err_code"] == ERR_NETWORK_TIMEOUT else "请检查URL和网络连接"
        llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=error_info["err_code"], detail=error_info["detail"], hint=_hint, timeout=timeout, proxy=proxy, headers=headers, body=body)
        return build_error(data={}, llm_data=llm_data)