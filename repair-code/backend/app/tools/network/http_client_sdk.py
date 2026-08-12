# -*- coding: utf-8 -*-
"""
Network HTTP 客户端 SDK
Author: 小沈 - 2026-05-29

基础模块,被 network tools 调用。
只处理任意 HTTP 端点,不处理 LLM 调用。
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
# 编辑历史:
# 2026-08-12 - 小欧 - 新增公用函数 is_ssrf_blocked_error: 识别httpx.InvalidURL(SSRF重定向拦截)并返回统一结构化错误信息,
#   供 httpget/fetch_webpage/download 三个网络工具复用(原各自手写isinstance分支, DRY统一)
# 2026-08-12 - 小欧 - _validate_redirect 新增 InvalidURL 抛出的文案标识前缀 "重定向目标被拦截", 供 is_ssrf_blocked_error 语义识别

import os
from typing import Optional

from urllib.parse import urljoin

import httpx
from app.tools.validate.url_validator import validate_url


# 常量已迁移到 tool_constants.py — 北京老陈 2026-05-30
from app.tools.tool_constants import DEFAULT_TIMEOUT_SEC, NETWORK_MAX_CONNECTIONS, NETWORK_MAX_KEEPALIVE
from app.tools.tool_constants import ERR_INVALID_URL

# SSRF重定向拦截文案标识 — 小欧 2026-08-12 (_validate_redirect 抛出的 InvalidURL 统一带此前缀)
_SSRF_REDIRECT_MARK = "重定向目标被拦截"


def is_ssrf_blocked_error(error: Exception) -> Optional[dict]:
    """判断异常是否为 SSRF 重定向拦截(httpx.InvalidURL) — 小欧 2026-08-12

    三个网络工具(httpget/fetch_webpage/download)统一复用:
    - httpx.InvalidURL 不经 RequestError/HTTPError 继承链(直接继承 Exception), 需显式捕获
    - _validate_redirect 在 response hook 中对重定向到回环/内网地址抛 httpx.InvalidURL(SSRF主动防护)
    - 属预期防护, 不应落入 catch-all 记 ERROR; 返回统一结构化错误信息供 build_error 使用

    Args:
        error: 捕获的异常

    Returns:
        dict(err_code/detail/hint) 若为 SSRF 拦截; None 否则
    """
    if isinstance(error, httpx.InvalidURL) and _SSRF_REDIRECT_MARK in str(error):
        return {
            "err_code": ERR_INVALID_URL,
            "detail": f"URL安全拦截: {error}",
            "hint": "该URL或其重定向目标被安全策略拦截, 请更换访问地址",
        }
    return None


def resolve_proxy(proxy: Optional[str] = None) -> Optional[str]:
    """
    统一代理解析

    优先级:proxy参数 > HTTPS_PROXY环境变量 > HTTP_PROXY环境变量
    """
    return proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


class HTTPClient:
    """HTTP 客户端实例(上下文管理器)"""

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

    @staticmethod
    async def _validate_redirect(response):
        if 300 <= response.status_code < 400:
            location = response.headers.get("location")
            if location:
                redirect_url = urljoin(str(response.url), location)
                is_valid, err, _ = validate_url(redirect_url)
                if not is_valid:
                    # 文案带 _SSRF_REDIRECT_MARK 前缀, 供 is_ssrf_blocked_error 语义识别 — 小欧 2026-08-12
                    raise httpx.InvalidURL(f"重定向目标被拦截: {err or 'URL无效'}")

    async def __aenter__(self):
        proxy_url = resolve_proxy(self._proxy)
        limits = httpx.Limits(
            max_connections=NETWORK_MAX_CONNECTIONS,
            max_keepalive_connections=NETWORK_MAX_KEEPALIVE,
        )
        timeout = httpx.Timeout(self._timeout_sec, connect=min(self._timeout_sec, 10.0))
        self._client = httpx.AsyncClient(
            verify=self._verify_ssl,
            timeout=timeout,
            limits=limits,
            follow_redirects=self._follow_redirects,
            proxy=proxy_url if proxy_url else None,
            event_hooks={"response": [self._validate_redirect]},
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
        """获取响应流(返回 async context manager)— 用于流式下载等需要逐块处理响应的场景"""
        return self._client.stream(method, url, **kwargs)

    async def download(
        self,
        url: str,
        save_path: str,
        chunk_size: int = 8192,
    ) -> int:
        """
        流式下载文件

        【设计说明】download() 返回 int(下载字节数),消费者无法像 get()/post() 那样
        在调用后检查 response.status_code。因此内部必须调用 raise_for_status(),
        让 httpx 异常(HTTPStatusError)传播给消费者统一处理。
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
        timeout_sec: 超时秒数,默认 30
        proxy: 代理地址(可选)。None 时从环境变量读取
        verify_ssl: 是否验证 SSL 证书,默认 True
        follow_redirects: 是否跟随重定向,默认 True

    Returns:
        HTTPClient 上下文管理器

    使用方式:
        async with create_http_client(timeout_sec=30) as client:
            response = await client.get("https://example.com")
    """
    return HTTPClient(
        timeout_sec=timeout_sec,
        proxy=proxy,
        verify_ssl=verify_ssl,
        follow_redirects=follow_redirects,
    )
