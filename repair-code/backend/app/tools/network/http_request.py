# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - #3 http请求异常详情丢失修复为类型:repr兜底
# 2026-07-15 - 小欧 - 常量归一化治理: JSON body 预览截断改引用 tool_constants.HTTP_JSON_PREVIEW_MAX_BYTES(原 _MAX_JSON_SIZE=10MB), 功能零退化
# 2026-07-16 - 小欧 - 修复双层except吞异常(HTTP错误结构化返回LLM/429工具内Retry-After契约重试一次/瞬时故障抛引擎重试)+hint精准化
# 2026-07-20 - 小欧 - httpget 门限治理(章9.4): HTTP_JSON_PREVIEW_MAX_BYTES 依3.5改名 HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES(保留为3.4硬安全网防OOM); 删本地重复定义, 截断触发置 _truncated+_reason(显示域截断收口于 OBS_HTTPGET_MAX_ROWS/CHARS)
# 2026-07-20 - 小欧 - httpget ②修复: data 超限时不内联5MB全文, 改200KB预览+_reason; HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES 下调至5MB
# 2026-07-23 - 小欧 - 新增 httpx.UnsupportedProtocol 异常处理(不支持的协议时返回结构化error, 不抛引擎)
# 2026-07-25 - 小欧 - 新增URL非ASCII字符预检: httpx无法处理非ASCII URL, 在参数校验阶段拦截返结构化错误; 异常兜底补UnicodeEncodeError/UnicodeDecodeError拦截
# 2026-07-25 - 小欧 - 新增Header非ASCII预检: httpx无法处理非ASCII Header值, 在create_http_client前拦截返结构化错误; 外层UnicodeEncodeError提示改通用(原只说URL, header也可能逃逸到此)
# 2026-07-25 - 小欧 - 【重构】URL非ASCII处理: 拦截报错→转码(IDNA+percent-encoding), RFC 3987标准IRI→URI转换, 中文域名/路径自动兼容; _transcode_url函数抽离; 转码后走validate_url做DNS/SSRF安全检查
# 2026-07-25 - 小欧 - 重构: _transcode_url 移入 validate/url_validator.py 作为公用函数 transcode_url(download/fetch_webpage 同用)
# 2026-07-25 - 小欧 - 【重构】Header非ASCII处理: 拦截报错→值自动转码(UTF-8→latin-1, HTTP标准兼容方式), 键仍强制ASCII(RFC 7230)
# 2026-08-06 - 小欧 - 核查7/31未实现项[21]修复: Header值非ASCII由UTF-8→latin-1转码改为拒绝(与键处理对称, RFC 9110 Header须ASCII, 避免字节漂移致服务端解码错乱), 声称功能"转码改拒绝"
# 2026-08-06 - 小欧 - 三堂会审修复: BUG-4 detail文案去"obs-text"暗示, 统一为"必须为ASCII"
# 2026-08-06 - 小欧 - 核查8-05/8-06日志: url=None 在非ASCII转码块 url.encode 抛AttributeError落入catch-all记"意外错误"; 入口加url=None显式拦截(fetch_webpage同模式, 三网络工具统一), 返回ERR_INVALID_URL结构化错误, 不再落入catch-all
# 2026-08-07 - 小欧 - BUG-02修复: headers仅接受dict, 防LLM传list引发 dict.update(list) ValueError
#   【病根】coerce_json(headers)可能返回list, request_headers.update(list) 抛 ValueError: dictionary update sequence(日志09:05:38)
#   【改法】if headers and isinstance(headers, dict): 才 update; 非dict自动忽略, 不抛异常(无退化)
# 2026-08-12 - 小欧 - 修复: httpget兜底except将httpx.InvalidURL(重定向目标被拦截=SSRF主动防护)记ERROR, 触发E2E"日志无非安全ERROR"断言失败
#   【病根】http_client_sdk._validate_redirect对重定向到回环/内网地址抛httpx.InvalidURL(SSRF防护), 落入catch-all记"意外错误"ERROR级, 语义错误(属预期防护)
#   【改法】显式捕获httpx.InvalidURL, 返回结构化错误(ERR_INVALID_URL)+warning日志, 不再记ERROR
# 2026-08-12 - 小欧 - 三堂会审DRY: InvalidURL识别统一改用http_client_sdk.is_ssrf_blocked_error公用函数(httpget/fetch_webpage/download三工具一致)
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
from app.tools.network.http_client_sdk import create_http_client, is_ssrf_blocked_error
from app.tools.network.network_register import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy, transcode_url
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
    HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES,
    HTTPGET_OUTLIMIT_DATA_PREVIEW_CHARS,
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


# 2026-07-20 - 小欧 - httpget 门限治理(章9.4): 删本地重复定义(改引用 tool_constants.HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES, 3.4 硬安全网); 截断触发置 _truncated+_reason


def _parse_response_body(response: httpx.Response) -> Dict[str, Any]:
    """解析HTTP响应体 — 小欧 2026-06-22 — 小欧 2026-06-24 增加JSON大小限制"""
    content_type = response.headers.get("content-type", "")
    content_type_short = content_type.split(";")[0].strip() if content_type else "unknown"

    if "application/json" in content_type:
        if len(response.content) > HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES:
            full_preview = response.text[:HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES]
            preview_for_data = full_preview[:HTTPGET_OUTLIMIT_DATA_PREVIEW_CHARS]
            body = {"_truncated": True, "_reason": "响应体超过安全上限(5MB), 仅展示预览片段(~200KB), 其余已截断", "_preview": preview_for_data}
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

    if url is None:
        llm_data = _build_http_request_llm_data("error", 0, "", method, err_code=ERR_INVALID_URL, detail="URL不能为空", hint="请提供要请求的URL", timeout=timeout, proxy=proxy, headers=headers, body=body)
        return build_error(data={}, llm_data=llm_data)

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
        # 非ASCII URL转码(IDNA+percent-encoding) — 小欧 2026-07-25
        # 将中文域名/路径等转成ASCII等效形式供httpx处理, 不拦截报错
        try:
            url.encode("ascii")
        except (UnicodeEncodeError, UnicodeDecodeError):
            url = transcode_url(url)

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
        # BUG-02修复: headers仅接受dict, 防LLM传list引发 dict.update(list) ValueError — 小欧 2026-08-07
        #   日志证据: 09:05:38 http_request.py:343 ValueError: dictionary update sequence
        if headers and isinstance(headers, dict):
            request_headers.update(headers)

# Header非ASCII字符拒绝 — 小欧 2026-07-25 — 2026-08-06 小欧: 值由转码改为拒绝(与键对称)
        # 键/值: RFC要求ASCII-only, 非ASCII则报错, 不再UTF-8→latin-1转码(避免字节漂移致服务端解码错乱)
        if request_headers:
            _new_headers = {}
            for _hk, _hv in request_headers.items():
                try:
                    _hk.encode("ascii")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                           err_code=ERR_NETWORK_INVALID_PARAM,
                                                           detail="HTTP Header 名称包含非ASCII字符, RFC 7230 规定 Header 名称必须为 ASCII",
                                                           hint="Header 名称请使用纯 ASCII 字符",
                                                           timeout=timeout, proxy=proxy, headers=headers, body=body)
                    return build_error(data={"error_detail": "Header名称包含非ASCII字符", "params": {"url": url}}, llm_data=llm_data)
                if _hv is not None:
                    try:
                        _hv.encode("ascii")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                        llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                               err_code=ERR_NETWORK_INVALID_PARAM,
                                                               detail=f"HTTP Header 值包含非ASCII字符: {_hk}(RFC 7230 规定 Header 值必须为 ASCII)",
                                                               hint=f"Header {_hk} 的值请使用纯 ASCII 字符",
                                                               timeout=timeout, proxy=proxy, headers=headers, body=body)
                        return build_error(data={"error_detail": f"Header值包含非ASCII字符: {_hk}", "params": {"url": url}}, llm_data=llm_data)
                _new_headers[_hk] = _hv
            request_headers = _new_headers

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
                if isinstance(e, httpx.UnsupportedProtocol):
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                           err_code=ERR_NETWORK_REQUEST_ERROR,
                                                           detail=f"httpx不支持 {url} 的协议",
                                                           hint="请使用http或https协议",
                                                           timeout=timeout, proxy=proxy, headers=headers, body=body)
                    return build_error(
                        data={"error_detail": "不支持的协议", "params": {"url": url}},
                        llm_data=llm_data)
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
        # UnicodeEncodeError: httpx内部编码异常(URL/Header预检未能覆盖的意外逃逸, URL已先经_transcode_url转码) — 小欧 2026-07-25
        if isinstance(e, (UnicodeEncodeError, UnicodeDecodeError)):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_http_request_llm_data("error", duration_ms, url, method,
                                                   err_code=ERR_NETWORK_INVALID_PARAM,
                                                   detail="请求参数包含不支持的字符编码",
                                                   hint="请使用ASCII字符或百分号编码",
                                                   timeout=timeout, proxy=proxy, headers=headers, body=body)
            return build_error(data={"error_detail": "请求参数包含不支持的字符编码", "params": {"url": url}}, llm_data=llm_data)
        # httpx.InvalidURL: URL/重定向目标校验失败(SSRF主动防护, 如重定向到回环/内网地址被拦截) — 小欧 2026-08-12
        # 【病根】原落入catch-all记"意外错误"ERROR级, 语义错误(属预期防护); 现显式捕获返结构化错误+warning
        # 三堂会审: 识别逻辑统一用 http_client_sdk.is_ssrf_blocked_error 公用函数 — 小欧 2026-08-12
        _ssrf_info = is_ssrf_blocked_error(e)
        if _ssrf_info:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            logger.warning(f"[httpget] URL安全拦截(SSRF防护): {e}")
            llm_data = _build_http_request_llm_data(
                "error", duration_ms, url, method,
                err_code=_ssrf_info["err_code"],
                detail=_ssrf_info["detail"],
                hint=_ssrf_info["hint"],
                timeout=timeout, proxy=proxy, headers=headers, body=body,
            )
            return build_error(
                data={"error_detail": _ssrf_info["detail"], "params": {"url": url}},
                llm_data=llm_data,
            )
        err_msg = f"{type(e).__name__}: {str(e) or repr(e)}"  # — 小欧 2026-07-13
        logger.error(f"[httpget] 意外错误: {err_msg}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _build_http_error(e, url, 0, duration_ms)
        _hint = "可增大timeout参数重试" if error_info["err_code"] == ERR_NETWORK_TIMEOUT else "请检查URL和网络连接"
        llm_data = _build_http_request_llm_data("error", duration_ms, url, method, err_code=error_info["err_code"], detail=error_info["detail"], hint=_hint, timeout=timeout, proxy=proxy, headers=headers, body=body)
        return build_error(data={}, llm_data=llm_data)
