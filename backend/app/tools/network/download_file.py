# -*- coding: utf-8 -*-
"""
N2: download — 下载文件到本地

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _stream_download / _map_network_error 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import os
import time as _time_mod
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client, HTTPClient
from app.tools.network.network_register import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy
from app.tools.validate.timeout_validator import validate_timeout
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory

from app.utils.logger import logger
from app.utils.paths import get_default_project_root

_DOWNLOAD_DIR = os.path.join(get_default_project_root(), "download")
_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
from app.tools.tool_constants import (
    ERR_INVALID_URL,
    ERR_NETWORK_CREATE_DIR,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_INVALID_PATH,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NETWORK_WRITE_FILE,
    ERR_NET_UNKNOWN,
)


def _build_download_file_llm_data(
    exec_code: str, duration_ms: int, url: str = "", dest_path: str = "",
    file_size: int = 0, total_size: int = 0, content_type: str = "",
    err_code: str = "", detail: str = "", hint: str = "",
    timeout: int = 60, proxy: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """download_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 过滤None值"""
    _act_params = {"url": url, "destination_path": dest_path, "timeout": timeout}
    if proxy is not None:
        _act_params["proxy"] = proxy
    if headers is not None:
        _act_params["headers"] = headers
    if exec_code == "error":
        return {
            "summary": f"下载文件{url}，失败",
            "action": {"tool": "download", "tool_zh": "文件下载", "target": url, "params": _act_params},
            "status": {"exec_code": "error", "message": "文件下载失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查URL和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    size_str = f"{file_size}字节" if file_size else ""
    type_str = f", {content_type}" if content_type else ""
    summary = f"下载并成功保存文件{dest_path},文件信息:" + (f":大小: {size_str}类型:{type_str}" if size_str or type_str else "")
    return {
        "summary": summary,
        "action": {"tool": "download", "tool_zh": "文件下载", "target": url, "params": _act_params},
        "status": {"exec_code": "success", "message": "文件下载成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"file_size": {"value": file_size, "text": size_str}, "content_type": {"value": content_type, "text": content_type}},
    }


_NET_ERROR_MAP = [
    (httpx.TimeoutException, ERR_NETWORK_TIMEOUT, "下载超时"),
    (httpx.HTTPStatusError, ERR_NETWORK_HTTP_ERROR, "下载失败"),
    (httpx.RequestError, ERR_NETWORK_REQUEST_ERROR, "网络请求失败"),
]


def _map_network_error(url: str, timeout: int, e: Exception, dest_path: str = "", duration_ms: int = 0) -> Dict[str, Any]:
    """将httpx异常映射为错误信息字典 — 小欧 2026-06-22"""
    for exc_type, code, prefix in _NET_ERROR_MAP:
        if isinstance(e, exc_type):
            detail = f"{prefix}({timeout}秒):{url}"
            if isinstance(e, httpx.HTTPStatusError):
                detail = f"{prefix} (HTTP {e.response.status_code}):{url}"
            return {"error_detail": detail, "params": {"url": url, "destination_path": dest_path, "timeout": timeout}, "err_code": code, "detail": detail}
    logger.error(f"[download] 未知错误: {e}")
    return {"error_detail": str(e), "params": {"url": url, "destination_path": dest_path, "timeout": timeout}, "err_code": ERR_NET_UNKNOWN, "detail": str(e)}


async def _stream_download(client: HTTPClient, url: str, dest_path: str,
                           headers: dict, chunk_size: int = 8192) -> Tuple[int, str, int]:
    """流式下载文件到本地 — 小欧 2026-06-22 — 小欧 2026-06-24 增加大小限制+清理"""
    async with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        raw_total = response.headers.get("content-length")
        total_bytes = int(raw_total) if raw_total else 0

        if raw_total and int(raw_total) > _MAX_FILE_SIZE:
            raise ValueError(f"文件过大: {raw_total}字节, 限制: {_MAX_FILE_SIZE}字节")

        downloaded = 0
        try:
            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    downloaded += len(chunk)
                    if downloaded > _MAX_FILE_SIZE:
                        raise ValueError(f"下载超过大小限制({_MAX_FILE_SIZE}字节)")
                    f.write(chunk)
        except Exception:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception:
                logger.warning(f"[download] 清理失败: {dest_path}")
            raise
        return downloaded, content_type, total_bytes if raw_total else downloaded


async def download(
    url: str,
    destination_path: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """从URL下载文件 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "download")
    if not timeout_valid:
        llm_data = _build_download_file_llm_data("error", 0, url, dest_path=destination_path or "", err_code=ERR_INVALID_URL, detail=timeout_err, hint="请检查超时设置", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_download_file_llm_data("error", 0, url, dest_path=destination_path or "", err_code=ERR_INVALID_URL, detail=proxy_err, hint="请检查代理配置", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)

    if destination_path is not None:
        if not isinstance(destination_path, str) or not destination_path.strip():
            llm_data = _build_download_file_llm_data("error", 0, url, dest_path="", err_code=ERR_NETWORK_INVALID_PATH, detail="destination_path不能为空", hint="请填写目标路径或留空自动命名", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        if any(p == ".." for p in destination_path.replace("\\", "/").split("/")):
            llm_data = _build_download_file_llm_data("error", 0, url, dest_path=destination_path, err_code=ERR_NETWORK_INVALID_PATH, detail="destination_path不允许路径遍历", hint="请使用合法文件名", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        dest_path = os.path.abspath(os.path.join(_DOWNLOAD_DIR, destination_path.lstrip("/\\")))
    else:
        filename = os.path.basename(urlparse(url).path) or f"download_{hash(url) & 0xFFFFFFFF}"
        dest_path = os.path.abspath(os.path.join(_DOWNLOAD_DIR, filename))
    # 工具层校验：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid_path, path_err, path_warn = validate_path(OpCategory.WRITE, dest_path)
    if not is_valid_path:
        llm_data = _build_download_file_llm_data("error", 0, url, dest_path=dest_path, err_code=ERR_NETWORK_INVALID_PATH, detail=path_err, hint="请检查目标路径", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    if path_warn:
        logger.warning(f"[download] {path_warn}")

    t0 = _time_mod.perf_counter()
    try:
        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            detail = error_msg or "URL格式无效"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_INVALID_URL, detail=detail, hint="请检查URL格式", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[download] {warning_msg}")
        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_DOWN, detail="网络不可用", hint="请检查网络连接", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)


        if not dest_path.startswith(os.path.abspath(_DOWNLOAD_DIR)):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_INVALID_PATH, detail="路径遍历不允许", hint="请检查目标路径", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        dest_dir = os.path.dirname(dest_path)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_CREATE_DIR, detail=str(e), hint="检查目标目录权限", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)

        req_headers = headers or {}

        if os.path.exists(dest_path) and os.path.realpath(dest_path) != os.path.abspath(dest_path):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_INVALID_PATH, detail="路径被篡改(symlink)", hint="请检查目标路径", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)

        async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
            downloaded, content_type, total_bytes = await _stream_download(client, url, dest_path, req_headers)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        # =============================================================================
        # 数据设计：file_path/total_size/content_type 全部通过 llm_data.summary 传入
        # summary 示例: "文件下载成功: /path/file.zip (1024000字节, application/zip)"
        # data = {}，无需额外字段 — 小欧 2026-07-06
        # =============================================================================
        llm_data = _build_download_file_llm_data("success", duration_ms, url, dest_path, downloaded, total_bytes, content_type, timeout=timeout, proxy=proxy, headers=headers)
        # ---- observation_formatter route -------------------------------------------
        # branch: A-#0 empty data — 无字段，输出"详情:\n" + 空
        # trigger: data == {}
        # handler: _format_scalar_data(data) — 空dict输出空字符串
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)
    except (PermissionError, OSError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_NETWORK_WRITE_FILE, detail=str(e), hint="请检查磁盘空间和权限", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _map_network_error(url, timeout, e, dest_path, duration_ms)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=error_info["err_code"], detail=error_info["detail"], hint="请检查URL和网络连接", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[download] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_NET_UNKNOWN, detail=str(e), hint="请检查URL和网络连接", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)