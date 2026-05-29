# -*- coding: utf-8 -*-
"""
Network HTTP 客户端 SDK
Author: 小沈 - 2026-05-29

基础模块，被 network tools 调用。
只处理任意 HTTP 端点，不处理 LLM 调用。
"""

import os
from typing import Optional

import httpx


# 集中配置
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_MAX_CONNECTIONS = 100
DEFAULT_MAX_KEEPALIVE = 20


def resolve_proxy(proxy: Optional[str] = None) -> Optional[str]:
    """
    统一代理解析

    优先级：proxy参数 > HTTPS_PROXY环境变量 > HTTP_PROXY环境变量
    """
    return proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


class HTTPClient:
    """HTTP 客户端实例（上下文管理器）"""

    def __init__(
        self,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        proxy: Optional[str] = None,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
    ):
        self._timeout_sec = timeout_sec
        self._proxy = proxy
        self._verify_ssl = verify_ssl
        self._follow_redirects = follow_redirects
        self._client = None

    async def __aenter__(self):
        proxy_url = resolve_proxy(self._proxy)
        limits = httpx.Limits(
            max_connections=DEFAULT_MAX_CONNECTIONS,
            max_keepalive_connections=DEFAULT_MAX_KEEPALIVE,
        )
        timeout = httpx.Timeout(self._timeout_sec, connect=min(self._timeout_sec, 10.0))
        self._client = httpx.AsyncClient(
            verify=self._verify_ssl,
            timeout=timeout,
            limits=limits,
            follow_redirects=self._follow_redirects,
            proxy=proxy_url if proxy_url else None,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """发送 GET 请求"""
        return await self._client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """发送 POST 请求"""
        return await self._client.post(url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """发送 DELETE 请求"""
        return await self._client.delete(url, **kwargs)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """发送任意方法的 HTTP 请求"""
        return await self._client.request(method, url, **kwargs)

    def stream(self, method: str, url: str, **kwargs):
        """获取响应流（返回 async context manager）— 用于流式下载等需要逐块处理响应的场景"""
        return self._client.stream(method, url, **kwargs)

    async def download(
        self,
        url: str,
        save_path: str,
        chunk_size: int = 8192,
    ) -> int:
        """
        流式下载文件

        【设计说明】download() 返回 int（下载字节数），消费者无法像 get()/post() 那样
        在调用后检查 response.status_code。因此内部必须调用 raise_for_status()，
        让 httpx 异常（HTTPStatusError）传播给消费者统一处理。
        这与 SDK "不做自定义错误处理"的原则不矛盾 — raise_for_status() 是 httpx 内置行为。

        Args:
            url: 下载地址
            save_path: 保存路径
            chunk_size: 分块大小

        Returns:
            下载的字节数
        """
        bytes_downloaded = 0
        async with self._client.stream("GET", url) as response:
            response.raise_for_status()
            with open(save_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
        return bytes_downloaded


def create_http_client(
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    proxy: Optional[str] = None,
    verify_ssl: bool = True,
    follow_redirects: bool = True,
) -> HTTPClient:
    """
    创建 HTTP 客户端 — 唯一入口

    Args:
        timeout_sec: 超时秒数，默认 30
        proxy: 代理地址（可选）。None 时从环境变量读取
        verify_ssl: 是否验证 SSL 证书，默认 True
        follow_redirects: 是否跟随重定向，默认 True

    Returns:
        HTTPClient 上下文管理器

    使用方式：
        async with create_http_client(timeout_sec=30) as client:
            response = await client.get("https://example.com")
    """
    return HTTPClient(
        timeout_sec=timeout_sec,
        proxy=proxy,
        verify_ssl=verify_ssl,
        follow_redirects=follow_redirects,
    )
