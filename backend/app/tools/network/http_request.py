# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - #3 http请求异常详情丢失修复为类型:repr兜底
# 2026-07-15 - 小欧 - 常量归一化治理: JSON body 预览截断改引用 tool_constants.HTTP_JSON_PREVIEW_MAX_BYTES(原 _MAX_JSON_SIZE=10MB), 功能零退化
# 2026-07-16 - 小欧 - 修复双层except吞异常(HTTP错误结构化返回LLM/429工具内Retry-After契约重试一次/瞬时故障抛引擎重试)+hint精准化
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
import asyncio
from datetime import datetime
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
    HTTP_JSON_PREVIEW_MAX_BYTES,
)




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


HTTP_JSON_PREVIEW_MAX_BYTES = 10 * 1024 * 1024  # 10MB


def _parse_response_body(response: httpx.Response) -> Dict[str, Any]:
    """解析HTTP响应体 — 小欧 2026-06-22 — 小欧 2026-06-24 增加JSON大小限制"""
    content_type = response.headers.get("content-type", "")
    content_type_short = content_type.split(";")[0].strip() if content_type else "unknown"

    if "application/json" in content_type:
        if len(response.content) > HTTP_JSON_PREVIEW_MAX_BYTES:
            body = {"_truncated": True, "_preview": response.text[:HTTP_JSON_PREVIEW_MAX_BYTES]}
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


def _parse_retry_after(header_value):
    """解析 429 响应的 Retry-After 头为等待秒数 — 小欧 2026-07-16
    支持整数秒(如 '30')或 HTTP 日期; 不可解析或超上限(>60s)返回 None, 交由上层决定。"""
    if not header_value:
        return None
    header_value = header_value.strip()
    try:
        _sec = float(header_value)
        if _sec < 0 or _sec > 60:
            return None
        return _sec
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        _dt = parsedate_to_datetime(header_value)
        if _dt is None:
            return None
        _now = datetime.now(_dt.tzinfo) if _dt.tzinfo else datetime.now()
        _delta = (_dt - _now).total_seconds()
        if _delta < 0 or _delta > 60:
            return None
        return _delta
    except Exception:
        return None


def _http_hint(status_code):
    """按 HTTP 状态码返回针对性 hint — 小欧 2026-07-16"""
    if status_code == 429:
        return "请求过于频繁(限流),请稍后重试或降低请求频率"
    if 400 <= status_code < 500:
        # hint不重复具体状态码(detail已有精确值,如"HTTP 403"),仅给可行动建议 — 小欧 2026-07-17
        return "客户端请求错误,请检查URL/请求方法与参数"
    if 500 <= status_code < 600:
        return "服务器暂时不可用,可稍后重试或换用其他地址"
    return "请检查URL和网络连接"


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
                # —— HTTP 状态码错误: 确定性结果, 结构化返回 LLM, 不抛引擎 — 小欧 2026-07-16
                # 仅 429 限流带 Retry-After 契约, 工具内按契约重试一次; 仍失败则回退结构化返回。
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                    if status_code == 429:
                        _ra = _parse_retry_after(e.response.headers.get("Retry-After"))
                        if _ra is not None:
                            logger.warning(f"[httpget] 收到429限流, 按Retry-After={_ra}s 契约重试一次: {url}")
                            await asyncio.sleep(_ra)
                            try:
                                response = await client.request(method_upper, **request_kwargs)
                                response.raise_for_status()
                                parsed = _parse_response_body(response)
                                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                                data = parsed["body"]
                                llm_data = _build_http_request_llm_data("success", duration_ms, url, method,
                                                                       response.status_code, parsed["content_type_short"],
                                                                       timeout=timeout, proxy=proxy, headers=headers, body=body)
                                return build_success(data=data, llm_data=llm_data)
                            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as _e2:
                                logger.warning(f"[httpget] 429重试后仍失败: {type(_e2).__name__}, 回退结构化返回")
                                e = _e2
                                status_code = _e2.response.status_code if isinstance(_e2, httpx.HTTPStatusError) else status_code
                    _hint = _http_hint(status_code)
                    try:
                        error_body = e.response.text
                    except Exception:
                        error_body = None
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                          err_code=ERR_NETWORK_HTTP_ERROR,
                                                          detail=f"HTTP {status_code}",
                                                          hint=_hint,
                                                          timeout=timeout, proxy=proxy, headers=headers, body=body)
                    return build_error(
                        data={"error_detail": f"HTTP {status_code}", "params": {"url": url, "status_code": status_code}},
                        llm_data=llm_data)
                # 超时/连接/传输等瞬时故障 → 抛给 ToolRetryEngine 重试 — 小欧 2026-07-16
                raise

    except Exception as e:
        # 仅兜底"真正的意外异常"; 瞬时故障(Timeout/RequestError)已在上方 raise, 此处再 raise 使其逃出 httpget 交 ToolRetryEngine — 小欧 2026-07-16
        # (修复原双层 except 吞掉可重试异常的 bug: 原 199 无差别吞 Exception 导致异常从未到引擎)
        if isinstance(e, (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError)):
            raise
        err_msg = f"{type(e).__name__}: {str(e) or repr(e)}"  # — 小欧 2026-07-13
        logger.error(f"[httpget] 意外错误: {err_msg}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _build_http_error(e, url, 0, duration_ms)
        _hint = "可增大timeout参数重试" if error_info["err_code"] == ERR_NETWORK_TIMEOUT else "请检查URL和网络连接"
        llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=error_info["err_code"], detail=error_info["detail"], hint=_hint, timeout=timeout, proxy=proxy, headers=headers, body=body)
        return build_error(data={}, llm_data=llm_data)