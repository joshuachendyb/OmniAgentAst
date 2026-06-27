# -*- coding: utf-8 -*-
"""
N2: download_file — 下载文件到本地

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

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client, HTTPClient
from app.tools.network.connectivity import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy
from app.tools.validate.timeout_validator import validate_timeout
from app.tools.validate.file_path_checker import validate_path_for_write

_check_network = check_network
_validate_url = validate_url
from app.utils.logger import logger

_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), ".omniagent", "downloads")
_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
from app.constants import (
    ERR_INVALID_URL,
    ERR_NETWORK_CONNECTION_ERROR,
    ERR_NETWORK_CREATE_DIR,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_DNS_ERROR,
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
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """download_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"文件下载失败: {url}",
            "action": {"tool": "download_file", "tool_zh": "文件下载", "target": url, "params": {"url": url}},
            "status": {"exec_code": "error", "message": "文件下载失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"文件下载成功: {dest_path}",
        "action": {"tool": "download_file", "tool_zh": "文件下载", "target": url, "params": {"url": url, "destination_path": dest_path}},
        "status": {"exec_code": "success", "message": "文件下载成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"file_size": {"value": file_size, "text": f"{file_size}字节"}},
    }


_NET_ERROR_MAP = [
    (httpx.TimeoutException, ERR_NETWORK_TIMEOUT, "下载超时"),
    (httpx.HTTPStatusError, ERR_NETWORK_HTTP_ERROR, "下载失败"),
    (httpx.RequestError, ERR_NETWORK_REQUEST_ERROR, "网络请求失败"),
]


def _map_network_error(url: str, timeout: int, e: Exception, duration_ms: int = 0) -> Dict[str, Any]:
    """将httpx异常映射为错误信息字典 — 小欧 2026-06-22"""
    for exc_type, code, prefix in _NET_ERROR_MAP:
        if isinstance(e, exc_type):
            detail = f"{prefix}({timeout}秒):{url}"
            if isinstance(e, httpx.HTTPStatusError):
                detail = f"{prefix} (HTTP {e.response.status_code}):{url}"
            return {"error_detail": detail, "params": {"url": url}, "err_code": code, "detail": detail}
    logger.error(f"[download_file] 未知错误: {e}")
    return {"error_detail": str(e), "params": {"url": url}, "err_code": ERR_NET_UNKNOWN, "detail": str(e)}


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
                pass
            raise
        return downloaded, content_type, total_bytes if raw_total else downloaded


async def download_file(
    url: str,
    destination_path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """从URL下载文件 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "download_file")
    if not timeout_valid:
        llm_data = _build_download_file_llm_data("error", 0, url, err_code=ERR_INVALID_URL, detail=timeout_err)
        return build_error(data={"error_detail": timeout_err, "params": {"url": url}}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_download_file_llm_data("error", 0, url, err_code=ERR_INVALID_URL, detail=proxy_err)
        return build_error(data={"error_detail": proxy_err, "params": {"proxy": proxy}}, llm_data=llm_data)

    dest_path = os.path.abspath(os.path.join(_DOWNLOAD_DIR, destination_path.lstrip("/\\")))
    is_valid_path, path_err, path_warn = validate_path_for_write(dest_path)
    if not is_valid_path:
        llm_data = _build_download_file_llm_data("error", 0, url, err_code=ERR_NETWORK_INVALID_PATH, detail=path_err)
        return build_error(data={"error_detail": path_err, "params": {"destination_path": destination_path}}, llm_data=llm_data)
    if path_warn:
        logger.warning(f"[download_file] {path_warn}")

    t0 = _time_mod.perf_counter()
    try:
        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            detail = error_msg or "URL格式无效"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_INVALID_URL, detail=detail)
            return build_error(data={"error_detail": detail, "params": {"url": url}}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[download_file] {warning_msg}")
        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用", "params": {"url": url}}, llm_data=llm_data)


        if not dest_path.startswith(os.path.abspath(_DOWNLOAD_DIR)):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_INVALID_PATH, detail="路径遍历不允许")
            return build_error(data={"error_detail": "路径遍历不允许", "params": {"path": destination_path}}, llm_data=llm_data)
        dest_dir = os.path.dirname(dest_path)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_CREATE_DIR, detail=str(e))
            return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)

        req_headers = headers or {}

        async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
            downloaded, content_type, total_bytes = await _stream_download(client, url, dest_path, req_headers)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"file_path": dest_path, "file_size": downloaded, "total_size": total_bytes if total_bytes > 0 else None, "content_type": content_type}
        llm_data = _build_download_file_llm_data("success", duration_ms, url, dest_path, downloaded, total_bytes, content_type)
        return build_success(data=data, llm_data=llm_data)
    except (PermissionError, OSError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_NETWORK_WRITE_FILE, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_path": dest_path}}, llm_data=llm_data)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _map_network_error(url, timeout, e, duration_ms)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=error_info["err_code"], detail=error_info["detail"])
        return build_error(data={"error_detail": error_info["error_detail"], "params": error_info["params"]}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[download_file] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)