# -*- coding: utf-8 -*-
"""
N2: download_file — 下载文件到本地

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _stream_download / _map_network_error 辅助函数
"""

import os
import time as _time_mod
from typing import Any, Dict, Optional, Tuple

import socket
import time
from urllib.parse import urlparse

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client, HTTPClient
from app.utils.logger import logger
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
            detail = f"{prefix}({timeout/1000}秒):{url}"
            if isinstance(e, httpx.HTTPStatusError):
                detail = f"{prefix} (HTTP {e.response.status_code}):{url}"
            return {"error_detail": detail, "params": {"url": url}, "err_code": code, "detail": detail}
    logger.error(f"[download_file] 未知错误: {e}")
    return {"error_detail": str(e), "params": {"url": url}, "err_code": ERR_NET_UNKNOWN, "detail": str(e)}


async def _stream_download(client: HTTPClient, url: str, dest_path: str,
                           headers: dict, chunk_size: int = 8192) -> Tuple[int, str, int]:
    """流式下载文件到本地 — 小欧 2026-06-22"""
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
) -> Dict[str, Any]:
    """从URL下载文件 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    dest_path = ""
    try:
        url_info = _validate_url(url)
        if not url_info["valid"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_INVALID_URL, detail="URL格式无效")
            return build_error(data={"error_detail": "URL格式无效", "params": {"url": url}}, llm_data=llm_data)
        net_info = _check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_DOWN, detail="网络不可用")
            return build_error(data={"error_detail": "网络不可用", "params": {"url": url}}, llm_data=llm_data)

        dest_path = os.path.abspath(destination_path)
        dest_dir = os.path.dirname(dest_path)
        if not dest_dir:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_INVALID_PATH, detail=f"无效路径: {destination_path}")
            return build_error(data={"error_detail": f"无效路径: {destination_path}", "params": {"path": destination_path}}, llm_data=llm_data)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, err_code=ERR_NETWORK_CREATE_DIR, detail=str(e))
            return build_error(data={"error_detail": str(e), "params": {"url": url}}, llm_data=llm_data)

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