# -*- coding: utf-8 -*-
"""
Network 工具函数模块 - 网络通信工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 register.py + Pydantic 模型注册

包含：
- http_request: 发起HTTP请求
- download_file: 下载文件到本地

返回格式：统一 {code, data, message} 格式
- code: SUCCESS 或 ERR_xxx 错误码
- data: 成功时返回数据，失败时为 None
- message: 描述信息

Author: 小沈 - 2026-04-29
"""

import os
import json
from typing import Optional, Dict, Any, Literal
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from app.utils.logger import logger


async def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
) -> dict:
    """
    发起HTTP请求

    支持 GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS 方法。
    支持自定义请求头、查询参数、请求体。
    支持超时控制和重定向跟随。
    """
    try:
        # 验证URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {
                "code": "ERR_NETWORK_INVALID_URL",
                "data": None,
                "message": f"无效的URL: {url}，URL必须包含协议和域名（如 https://api.example.com/data）"
            }

        # 处理查询参数
        if params:
            query_string = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=query_string))

        # 构建请求头
        request_headers = {}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=follow_redirects
        ) as client:
            # 根据method选择请求方式
            method_upper = method.upper()

            request_kwargs = {
                "url": url,
                "headers": request_headers,
            }

            # 处理请求体
            if method_upper in ("POST", "PUT", "PATCH"):
                if json_body is not None:
                    request_kwargs["json"] = json_body
                elif body is not None:
                    request_kwargs["content"] = body.encode("utf-8") if isinstance(body, str) else body

            response = await client.request(method_upper, **request_kwargs)
            response.raise_for_status()

            # 尝试解析响应体
            content_type = response.headers.get("content-type", "")
            response_body = None
            if "application/json" in content_type:
                try:
                    response_body = response.json()
                except (json.JSONDecodeError, ValueError):
                    response_body = response.text
            else:
                response_body = response.text

            return {
                "code": "SUCCESS",
                "data": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                },
                "message": f"请求成功 (HTTP {response.status_code})"
            }

    except httpx.TimeoutException:
        return {
            "code": "ERR_NETWORK_TIMEOUT",
            "data": None,
            "message": f"请求超时（{timeout}秒）：{url}"
        }
    except httpx.HTTPStatusError as e:
        try:
            error_body = e.response.text
        except Exception:
            error_body = None
        return {
            "code": "ERR_NETWORK_HTTP_ERROR",
            "data": {
                "status_code": e.response.status_code,
                "body": error_body,
            },
            "message": f"HTTP请求失败 (HTTP {e.response.status_code})：{url}"
        }
    except httpx.RequestError as e:
        return {
            "code": "ERR_NETWORK_REQUEST_ERROR",
            "data": None,
            "message": f"网络请求失败：{str(e)}"
        }
    except Exception as e:
        logger.error(f"[http_request] 未知错误: {e}")
        return {
            "code": "ERR_NETWORK_UNKNOWN",
            "data": None,
            "message": f"请求异常: {str(e)}"
        }


async def download_file(
    url: str,
    destination_path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 300,
    chunk_size: int = 8192,
) -> dict:
    """
    从URL下载文件到本地路径

    支持大文件流式下载。
    自动创建目标目录。
    支持超时控制和自定义请求头。
    """
    try:
        # 验证URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {
                "code": "ERR_NETWORK_INVALID_URL",
                "data": None,
                "message": f"无效的URL: {url}，URL必须包含协议和域名"
            }

        # 验证目标路径
        dest_path = os.path.abspath(destination_path)
        dest_dir = os.path.dirname(dest_path)
        if not dest_dir:
            return {
                "code": "ERR_NETWORK_INVALID_PATH",
                "data": None,
                "message": f"无效的目标路径: {destination_path}，路径必须包含目录"
            }

        # 创建目标目录
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            return {
                "code": "ERR_NETWORK_CREATE_DIR",
                "data": None,
                "message": f"无法创建目录 {dest_dir}: {str(e)}"
            }

        # 构建请求头
        request_headers = {}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True
        ) as client:
            async with client.stream("GET", url, headers=request_headers) as response:
                response.raise_for_status()

                # 获取文件信息
                total_size = int(response.headers.get("content-length", 0))
                content_type = response.headers.get("content-type", "")

                # 流式写入文件
                downloaded = 0
                try:
                    with open(dest_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)
                except (PermissionError, OSError) as e:
                    # 清理不完整的文件
                    try:
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                    except OSError:
                        pass
                    return {
                        "code": "ERR_NETWORK_WRITE_FILE",
                        "data": None,
                        "message": f"写入文件失败 {dest_path}: {str(e)}"
                    }

                return {
                    "code": "SUCCESS",
                    "data": {
                        "file_path": dest_path,
                        "file_size": downloaded,
                        "content_type": content_type,
                        "total_size": total_size,
                    },
                    "message": f"文件下载成功 ({downloaded} 字节)：保存到 {dest_path}"
                }

    except httpx.TimeoutException:
        return {
            "code": "ERR_NETWORK_TIMEOUT",
            "data": None,
            "message": f"下载超时（{timeout}秒）：{url}"
        }
    except httpx.HTTPStatusError as e:
        return {
            "code": "ERR_NETWORK_HTTP_ERROR",
            "data": None,
            "message": f"下载失败 (HTTP {e.response.status_code})：{url}"
        }
    except httpx.RequestError as e:
        return {
            "code": "ERR_NETWORK_REQUEST_ERROR",
            "data": None,
            "message": f"网络请求失败：{str(e)}"
        }
    except Exception as e:
        logger.error(f"[download_file] 未知错误: {e}")
        return {
            "code": "ERR_NETWORK_UNKNOWN",
            "data": None,
            "message": f"下载异常: {str(e)}"
        }
