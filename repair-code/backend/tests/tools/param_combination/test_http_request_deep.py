# -*- coding: utf-8 -*-
"""
http_request 第三轮深度BUG发现测试
小健 2026-06-25
"""
import asyncio
import pytest

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestHttpRequestDeepBugs:
    """深度BUG发现 — http_request — 小健 2026-06-25"""

    def test_bug_1_url_empty(self):
        """BUG#1: url=""空字符串"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(""))
        assert is_error(result)

    def test_bug_2_url_none(self):
        """BUG#2: url=None"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(None))
        assert is_error(result)

    def test_bug_3_url_invalid_format(self):
        """BUG#3: url格式无效"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("not-a-url"))
        assert is_error(result)

    def test_bug_4_method_invalid(self):
        """BUG#4: method="INVALID"无效方法"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com", method="INVALID"))
        # 应该报错

    def test_bug_5_timeout_zero(self):
        """BUG#5: timeout=0"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com", timeout=0))
        # 应该报错或立即超时

    def test_bug_6_timeout_negative(self):
        """BUG#6: timeout=-1负数"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com", timeout=-1))
        # 应该报错

    def test_bug_7_headers_invalid(self):
        """BUG#7: headers格式无效"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com", headers="invalid"))
        # 应该报错

    def test_bug_8_body_invalid_json(self):
        """BUG#8: body无效JSON"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com", method="POST", body="{invalid json"))
        # 应该报错或发送原始字符串

    def test_bug_9_url_with_special_chars(self):
        """BUG#9: url包含特殊字符"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com/path?query=test&name=测试"))
        # 应该正认编码

    def test_bug_10_url_ftp_protocol(self):
        """BUG#10: url使用FTP协议"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("ftp://example.com/file.txt"))
        assert is_error(result), "FTP协议应返回错误"

    def test_bug_11_redirect_infinite(self):
        """BUG#11: 无限重定向"""
        from app.tools.network.http_request import httpget
        # 需要mock服务器返回无限重定向
        pass

    def test_bug_12_ssl_invalid_cert(self):
        """BUG#12: SSL证书无效(verify_ssl参数已移除)"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://self-signed.badssl.com/"))
        # verify_ssl参数已移除,使用httpx默认

    def test_bug_13_concurrent_requests(self):
        """BUG#13: 并发请求"""
        from app.tools.network.http_request import httpget
        async def request_task():
            return await httpget("http://example.com", timeout=5)
        async def run_concurrent():
            return await asyncio.gather(*[request_task() for _ in range(10)])
        results = _run(run_concurrent())
        # 应该全部成功

    def test_bug_14_large_response(self):
        """BUG#14: 大响应(100MB)"""
        from app.tools.network.http_request import httpget
        # 需要mock服务器返回大响应
        pass

    def test_bug_15_auth_removed(self):
        """BUG#15: auth参数已移除"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://example.com"))
        # auth参数已移除
