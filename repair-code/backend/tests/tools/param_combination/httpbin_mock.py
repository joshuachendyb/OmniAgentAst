# -*- coding: utf-8 -*-
"""
本地 httpbin.org 模拟(mock) — 小欧 2026-07-12

httpbin.org 当前返回 503 不可用。为让依赖 httpbin.org 的测试稳定跑绿,
在测试侧 monkeypatch httpx.AsyncClient,注入路由 transport:
  - httpbin.org 主机 -> 本地模拟响应(模仿 httpbin 行为)
  - 其他主机 -> 真实网络(example.com / github.com 等仍可用)

不修改任何被测源码;仅在测试侧使用。
"""
import asyncio
import json

import httpx


_HTTPBIN_HTML = (
    "<html><head><title>Mock Page</title></head><body>"
    "<main><h1>Mock Heading</h1>"
    "<p>This is a sufficiently long mock HTML page body used by the local "
    "httpbin mock so that fetch_webpage extraction yields more than one "
    "hundred characters of plain text content for successful extraction.</p>"
    "<p>It contains multiple paragraphs and enough textual content to pass "
    "the minimum content length checks implemented in the fetchpage tool.</p>"
    "</main></body></html>"
)


class _RoutingTransport(httpx.AsyncBaseTransport):
    """路由 transport: httpbin.org 走本地模拟,其余走真实网络 — 小欧 2026-07-12"""

    def __init__(self):
        self._real = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        if request.url.host == "httpbin.org":
            return await self._mock(request)
        return await self._real.handle_async_request(request)

    async def _mock(self, request):
        method = request.method
        path = request.url.path

        # 非法 HTTP 方法 -> 405 (模仿 httpbin 行为)
        if method.upper() not in (
            "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE"
        ):
            return httpx.Response(405, request=request)

        # /delay/<n> : n>=10 触发超时,否则按 n 秒延时后返回 200
        if path.startswith("/delay/"):
            try:
                n = int(path.split("/")[2])
            except (IndexError, ValueError):
                n = 0
            if n >= 10:
                raise httpx.TimeoutException("mock httpbin delay timeout")
            await asyncio.sleep(min(n, 2))
            return self._json(200, {"url": str(request.url), "method": method})

        # /status/<code> : 原样返回状态码
        if path.startswith("/status/"):
            try:
                code = int(path.split("/")[2])
            except (IndexError, ValueError):
                code = 200
            return httpx.Response(code, request=request)

        # /bytes/<n> : 返回 n 字节(上限 1024)二进制流
        if path.startswith("/bytes/"):
            try:
                n = int(path.split("/")[2])
            except (IndexError, ValueError):
                n = 1024
            size = min(n, 1024)
            data = b"\x00" * size
            return httpx.Response(
                200,
                content=data,
                headers={
                    "content-type": "application/octet-stream",
                    "content-length": str(size),
                },
                request=request,
            )

        if path == "/robots.txt":
            body = b"User-agent: *\nDisallow:\n"
            return httpx.Response(
                200,
                content=body,
                headers={
                    "content-type": "text/plain",
                    "content-length": str(len(body)),
                },
                request=request,
            )

        if path == "/json":
            return self._json(200, {"slideshow": {"title": "Sample Slide Show"}})

        if path == "/headers":
            return self._json(200, {"headers": dict(request.headers)})

        if path == "/html":
            return httpx.Response(
                200,
                content=_HTTPBIN_HTML.encode("utf-8"),
                headers={
                    "content-type": "text/html; charset=utf-8",
                    "content-length": str(len(_HTTPBIN_HTML)),
                },
                request=request,
            )

        # /redirect/<n> : 直接当作成功(避免重定向链)
        if path.startswith("/redirect/"):
            return self._json(200, {"url": str(request.url), "method": method})

        # /basic-auth : 无凭证返回 401
        if path.startswith("/basic-auth"):
            return httpx.Response(401, request=request)

        # 默认回显(get/post/put/patch/delete)
        try:
            raw = request.content
        except Exception:
            raw = b""
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except Exception:
                parsed = raw.decode("utf-8", "replace")
        echo = {
            "url": str(request.url),
            "method": method,
            "args": dict(request.url.params),
            "headers": dict(request.headers),
            "json": parsed,
            "data": parsed if isinstance(parsed, str) else None,
        }
        return self._json(200, echo)

    @staticmethod
    def _json(status, payload):
        return httpx.Response(
            status,
            json=payload,
            headers={"content-type": "application/json"},
            request=None,
        )


_ROUTING = _RoutingTransport()


def install_httpbin_mock(monkeypatch):
    """monkeypatch httpx.AsyncClient 注入路由 transport — 小欧 2026-07-12

    仅替换 transport(丢弃 proxy / event_hooks),其余构造参数保留。
    """
    original_init = httpx.AsyncClient.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs.pop("proxy", None)
        kwargs.pop("event_hooks", None)
        kwargs.pop("transport", None)
        kwargs["transport"] = _ROUTING
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", _patched_init)
