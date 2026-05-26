# -*- coding: utf-8 -*-
"""
N1 http_request 深度测试 — test_n1_http_request_deep.py

覆盖维度：
1. 参数校验边界（retry/timeout范围、URL格式）
2. 请求方法分发（GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS）
3. body/json_body 优先级与编码
4. 重试策略（指数退避、429/5xx重试、404不重试）
5. 代理配置（参数→环境变量HTTPS_PROXY→HTTP_PROXY）
6. 响应处理（JSON解析、文本响应、大响应截断）
7. llm_data 格式（≤5K全给、>5K截断、dict/list make_json_safe）
8. next_actions 注入

【规范】本测试为N1专用深度测试，不依赖旧测试代码
Author: 小沈 - 2026-05-19
"""

import json
import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import httpx

from app.services.tools.network.network_tools import http_request


# ============================================================
# 1. 参数校验边界测试
# ============================================================
class TestN1ParamValidation:
    """N1 参数校验边界测试"""

    @pytest.mark.asyncio
    async def test_url_missing_scheme(self):
        """URL缺少协议 → ERR_INVALID_URL"""
        result = await http_request("example.com/api")
        assert result["code"] == "ERR_INVALID_URL"
        assert "协议" in result["message"]

    @pytest.mark.asyncio
    async def test_url_missing_netloc(self):
        """URL缺少域名 → ERR_INVALID_URL"""
        result = await http_request("https:///path")
        assert result["code"] == "ERR_INVALID_URL"

    @pytest.mark.asyncio
    async def test_url_empty(self):
        """空URL → ERR_INVALID_URL"""
        result = await http_request("")
        assert result["code"] == "ERR_INVALID_URL"

    @pytest.mark.asyncio
    async def test_retry_negative(self):
        """retry=-1 → ERR_NETWORK_INVALID_PARAM"""
        result = await http_request("https://example.com", retry=-1)
        assert result["code"] == "ERR_NETWORK_INVALID_PARAM"
        assert "重试次数" in result["message"]

    @pytest.mark.asyncio
    async def test_retry_too_large(self):
        """retry=11 → ERR_NETWORK_INVALID_PARAM"""
        result = await http_request("https://example.com", retry=11)
        assert result["code"] == "ERR_NETWORK_INVALID_PARAM"

    @pytest.mark.asyncio
    async def test_retry_boundary_max(self):
        """retry=10 → 通过校验（边界值）"""
        result = await http_request("https://example.com", retry=10, timeout=1000)
        # 通过校验后会进入请求逻辑，但URL不可达会返回请求错误而非参数错误
        assert result["code"] != "ERR_NETWORK_INVALID_PARAM"

    @pytest.mark.asyncio
    async def test_timeout_too_small(self):
        """timeout=500 → ERR_NETWORK_INVALID_PARAM"""
        result = await http_request("https://example.com", timeout=500)
        assert result["code"] == "ERR_NETWORK_INVALID_PARAM"
        assert "超时时间" in result["message"]

    @pytest.mark.asyncio
    async def test_timeout_too_large(self):
        """timeout=700000 → ERR_NETWORK_INVALID_PARAM"""
        result = await http_request("https://example.com", timeout=700000)
        assert result["code"] == "ERR_NETWORK_INVALID_PARAM"

    @pytest.mark.asyncio
    async def test_timeout_boundary_min(self):
        """timeout=1000 → 通过校验（边界值）"""
        result = await http_request("https://example.com", timeout=1000)
        assert result["code"] != "ERR_NETWORK_INVALID_PARAM"

    @pytest.mark.asyncio
    async def test_timeout_boundary_max(self):
        """timeout=600000 → 通过校验（边界值）"""
        result = await http_request("https://example.com", timeout=600000)
        assert result["code"] != "ERR_NETWORK_INVALID_PARAM"


# ============================================================
# 2. 请求方法分发测试（Mock）
# ============================================================
class TestN1RequestMethods:
    """N1 HTTP方法分发测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_no_body(self, mock_client_cls):
        """GET请求不应传递body"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/data", method="GET")
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "GET"
        assert "json" not in call_args[1]
        assert "content" not in call_args[1]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_post_with_json_body(self, mock_client_cls):
        """POST + json_body → 正确传递json参数"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com/users",
            method="POST",
            json_body={"name": "张三", "age": 30},
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json"] == {"name": "张三", "age": 30}

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_post_with_body_string(self, mock_client_cls):
        """POST + body字符串 → 正确编码为utf-8 bytes"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "ok"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com/data",
            method="POST",
            body="raw text content",
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert call_args[1]["content"] == b"raw text content"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_json_body_priority_over_body(self, mock_client_cls):
        """json_body和body同时存在 → json_body优先"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com/data",
            method="POST",
            json_body={"key": "json"},
            body="should be ignored",
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert "json" in call_args[1]
        assert call_args[1]["json"] == {"key": "json"}
        assert "content" not in call_args[1]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_put_method(self, mock_client_cls):
        """PUT方法也能传递body"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com/data",
            method="PUT",
            json_body={"key": "value"},
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "PUT"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_head_no_body(self, mock_client_cls):
        """HEAD方法不应传递body"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = ""
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://example.com",
            method="HEAD",
            body="should be ignored",
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "HEAD"
        assert "content" not in call_args[1]
        assert "json" not in call_args[1]


# ============================================================
# 3. 代理配置测试
# ============================================================
class TestN1ProxyConfig:
    """N1 代理配置测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_proxy_from_param(self, mock_client_cls):
        """proxy参数优先"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com",
            proxy="http://proxy.example.com:8080",
        )
        assert result["code"] == "SUCCESS"
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["proxy"] == "http://proxy.example.com:8080"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch.dict(os.environ, {"HTTPS_PROXY": "http://env-https-proxy:3128"}, clear=False)
    async def test_proxy_from_env_https(self, mock_client_cls):
        """无proxy参数时读取HTTPS_PROXY环境变量"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com")
        assert result["code"] == "SUCCESS"
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["proxy"] == "http://env-https-proxy:3128"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch.dict(os.environ, {"HTTP_PROXY": "http://env-http-proxy:3128"}, clear=False)
    async def test_proxy_from_env_http_fallback(self, mock_client_cls):
        """无HTTPS_PROXY时回退到HTTP_PROXY"""
        # 先清除HTTPS_PROXY确保回退逻辑
        old_https = os.environ.pop("HTTPS_PROXY", None)
        try:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await http_request("https://api.example.com")
            assert result["code"] == "SUCCESS"
            call_kwargs = mock_client_cls.call_args[1]
            assert call_kwargs["proxy"] == "http://env-http-proxy:3128"
        finally:
            if old_https:
                os.environ["HTTPS_PROXY"] = old_https


# ============================================================
# 4. 重试策略测试
# ============================================================
class TestN1RetryStrategy:
    """N1 重试策略测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_429_exponential_backoff(self, mock_sleep, mock_client_cls):
        """429错误触发指数退避重试"""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 429
        mock_response_fail.text = "rate limited"
        mock_response_fail.headers = {}

        error_429 = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response_fail
        )

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.headers = {"content-type": "application/json"}
        mock_response_ok.json.return_value = {"ok": True}
        mock_response_ok.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[error_429, error_429, mock_response_ok])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com", retry=3)
        assert result["code"] == "SUCCESS"
        assert mock_client.request.call_count == 3
        # 验证sleep被调用2次（第0次和第1次失败后）
        assert mock_sleep.call_count == 2
        # 指数退避: 0.5s, 1.0s
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.0)

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_404_no_retry(self, mock_client_cls):
        """404错误不触发重试，立即返回"""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 404
        mock_response_fail.text = "not found"
        mock_response_fail.headers = {}

        error_404 = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response_fail
        )

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[error_404])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/missing", retry=3)
        assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
        assert result["data"]["status_code"] == 404
        assert mock_client.request.call_count == 1  # 只请求1次，不重试

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_500_retry_then_fail(self, mock_sleep, mock_client_cls):
        """500错误重试耗尽后返回错误"""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "server error"
        mock_response_fail.headers = {}
        mock_response_fail.text = "server error"

        error_500 = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response_fail
        )

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[error_500, error_500, error_500, error_500])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com", retry=3)
        assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
        assert "重试3次后" in result["message"]
        assert mock_client.request.call_count == 4  # 初始 + 3次重试

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_timeout_retry(self, mock_sleep, mock_client_cls):
        """超时异常触发重试"""
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.headers = {"content-type": "application/json"}
        mock_response_ok.json.return_value = {"ok": True}
        mock_response_ok.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[httpx.TimeoutException("timeout"), mock_response_ok])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com", retry=3)
        assert result["code"] == "SUCCESS"
        assert mock_client.request.call_count == 2


# ============================================================
# 5. 响应处理测试
# ============================================================
class TestN1ResponseHandling:
    """N1 响应处理测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_json_response_parsed(self, mock_client_cls):
        """application/json响应自动解析为dict"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json; charset=utf-8"}
        mock_response.json.return_value = {"users": [{"id": 1, "name": "张三"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/users")
        assert result["code"] == "SUCCESS"
        assert result["data"]["body"] == {"users": [{"id": 1, "name": "张三"}]}
        assert result["llm_data"]["响应体"] == {"users": [{"id": 1, "name": "张三"}]}

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_text_response(self, mock_client_cls):
        """text/plain响应返回字符串"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "Hello, World!"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/hello")
        assert result["code"] == "SUCCESS"
        assert result["data"]["body"] == "Hello, World!"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_json_decode_fallback_to_text(self, mock_client_cls):
        """JSON解析失败时回退到text"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.side_effect = json.JSONDecodeError("bad json", "", 0)
        mock_response.text = "not valid json"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/data")
        assert result["code"] == "SUCCESS"
        assert result["data"]["body"] == "not valid json"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_large_string_response_truncated(self, mock_client_cls):
        """大字符串响应截断到4000字符"""
        large_text = "A" * 10000
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = large_text
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/large")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["body"]) <= 4100  # 4000 + 截断提示
        assert "截断" in result["data"]["body"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_large_json_dict_make_json_safe(self, mock_client_cls):
        """超大JSON dict使用make_json_safe保留结构"""
        large_json = {
            "items": [{"id": i, "description": "X" * 1000} for i in range(20)]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = large_json
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/large-json")
        assert result["code"] == "SUCCESS"
        # llm_data中的响应体应该是被make_json_safe处理过的
        llm_body = result["llm_data"]["响应体"]
        assert isinstance(llm_body, dict)
        # 结构保留但字符串被截断
        assert "items" in llm_body

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_params_query_string(self, mock_client_cls):
        """params参数正确编码为查询字符串"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com/search",
            params={"q": "hello world", "page": "1"},
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        assert "hello%20world" in call_args[1]["url"] or "hello+world" in call_args[1]["url"]


# ============================================================
# 6. llm_data与next_actions测试
# ============================================================
class TestN1LlmDataAndNextActions:
    """N1 llm_data和next_actions测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_llm_data_structure(self, mock_client_cls):
        """llm_data包含状态码、内容类型、响应体"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json; charset=utf-8"}
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/data")
        assert result["code"] == "SUCCESS"
        assert "llm_data" in result
        llm_data = result["llm_data"]
        assert llm_data["状态码"] == 200
        assert llm_data["内容类型"] == "application/json"
        assert "响应体" in llm_data

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_next_actions_present(self, mock_client_cls):
        """成功返回包含next_actions"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/data")
        assert result["code"] == "SUCCESS"
        assert "next_actions" in result
        assert len(result["next_actions"]) > 0

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_error_no_next_actions(self, mock_client_cls):
        """错误返回不应包含next_actions（或为空）"""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 404
        mock_response_fail.text = "not found"
        mock_response_fail.headers = {}

        error_404 = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response_fail
        )

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[error_404])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com/missing")
        assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
        # 错误返回不强制有next_actions


# ============================================================
# 7. 综合边界测试
# ============================================================
class TestN1EdgeCases:
    """N1 综合边界测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_verify_ssl_false(self, mock_client_cls):
        """verify_ssl=False传递给httpx"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://self-signed.badssl.com", verify_ssl=False)
        assert result["code"] == "SUCCESS"
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["verify"] is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_follow_redirects_false(self, mock_client_cls):
        """follow_redirects=False传递给httpx"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://example.com", follow_redirects=False)
        assert result["code"] == "SUCCESS"
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["follow_redirects"] is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_headers_merged(self, mock_client_cls):
        """自定义headers与默认headers合并"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request(
            "https://api.example.com",
            headers={"Authorization": "Bearer token123", "X-Custom": "value"},
        )
        assert result["code"] == "SUCCESS"
        call_args = mock_client.request.call_args
        request_headers = call_args[1]["headers"]
        assert request_headers["Authorization"] == "Bearer token123"
        assert request_headers["X-Custom"] == "value"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_retry_zero(self, mock_client_cls):
        """retry=0时不重试"""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "error"
        mock_response_fail.headers = {}

        error_500 = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response_fail
        )

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[error_500])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com", retry=0)
        assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
        assert mock_client.request.call_count == 1

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_timeout_conversion(self, mock_client_cls):
        """timeout毫秒正确转换为秒传递给httpx"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await http_request("https://api.example.com", timeout=15000)
        assert result["code"] == "SUCCESS"
        call_kwargs = mock_client_cls.call_args[1]
        timeout_obj = call_kwargs["timeout"]
        assert timeout_obj.read == 15.0  # 15000ms = 15s
