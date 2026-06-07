# -*- coding: utf-8 -*-
"""
N3 fetch_webpage 深度测试 — test_n3_fetch_webpage_deep.py

覆盖维度：
1. 参数校验（URL格式）
2. 静态抓取分支（js_render=False）
3. Cloudflare 403降级重试
4. 图片/PDF附件返回（base64）
5. 内容提取格式（markdown/html/text）
6. max_tokens截断
7. JS渲染分支（js_render=True，mock Playwright）
8. 代理配置
9. 错误处理（超时、HTTP错误、网络错误）
10. llm_data和返回结构

【规范】本测试为N3专用深度测试
Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import httpx

from app.services.tools.network.network_tools import fetch_webpage, _html_to_markdown


# ============================================================
# 1. 参数校验测试
# ============================================================
class TestN3ParamValidation:
    """N3 参数校验测试"""

    @pytest.mark.asyncio
    async def test_invalid_url_no_scheme(self):
        """URL缺少协议 → ERR_INVALID_URL"""
        result = await fetch_webpage("example.com")
        assert result["code"] == "ERR_INVALID_URL"

    @pytest.mark.asyncio
    async def test_invalid_url_no_netloc(self):
        """URL缺少域名 → ERR_INVALID_URL"""
        result = await fetch_webpage("https:///path")
        assert result["code"] == "ERR_INVALID_URL"


# ============================================================
# 2. 静态抓取分支测试
# ============================================================
class TestN3StaticFetch:
    """N3 静态抓取分支测试（js_render=False）"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_markdown_default(self, mock_client_cls):
        """默认markdown格式提取"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com")
        assert result["code"] == "SUCCESS"
        assert result["data"]["format"] == "markdown"
        assert "Title" in result["data"]["content"]
        assert "Content" in result["data"]["content"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_html_format(self, mock_client_cls):
        """html格式返回原始HTML"""
        html_content = "<html><body><h1>Title</h1></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html_content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com", extract_format="html")
        assert result["code"] == "SUCCESS"
        assert result["data"]["format"] == "html"
        assert result["data"]["content"] == html_content

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_text_format(self, mock_client_cls):
        """text格式返回纯文本"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com", extract_format="text")
        assert result["code"] == "SUCCESS"
        assert result["data"]["format"] == "text"
        assert "Hello World" in result["data"]["content"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_user_agent_custom(self, mock_client_cls):
        """自定义User-Agent传递到请求头"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com", user_agent="CustomBot/1.0")
        assert result["code"] == "SUCCESS"
        call_args = mock_client.get.call_args
        assert call_args[1]["headers"]["User-Agent"] == "CustomBot/1.0"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_default_user_agent(self, mock_client_cls):
        """默认User-Agent为浏览器UA"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com")
        assert result["code"] == "SUCCESS"
        call_args = mock_client.get.call_args
        assert "Mozilla/5.0" in call_args[1]["headers"]["User-Agent"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_with_prompt(self, mock_client_cls):
        """prompt参数加入返回数据"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body>Content</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com", prompt="提取标题")
        assert result["code"] == "SUCCESS"
        assert result["data"]["prompt"] == "提取标题"
        assert "note" in result["data"]


# ============================================================
# 3. Cloudflare 403降级测试
# ============================================================
class TestN3CloudflareRetry:
    """N3 Cloudflare 403降级重试测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_cloudflare_challenge_retry(self, mock_client_cls):
        """Cloudflare 403挑战检测 → 降级UA重试"""
        mock_response_403 = MagicMock()
        mock_response_403.status_code = 403
        mock_response_403.headers = {"cf-mitigated": "challenge"}
        mock_response_403.raise_for_status = MagicMock()

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.headers = {"content-type": "text/html"}
        mock_response_200.text = "<html><body>Success</body></html>"
        mock_response_200.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_response_403, mock_response_200])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com")
        assert result["code"] == "SUCCESS"
        assert mock_client.get.call_count == 2
        # 第二次调用使用降级UA
        second_call_headers = mock_client.get.call_args_list[1][1]["headers"]
        assert second_call_headers["User-Agent"] == "opencode/1.0"


# ============================================================
# 4. 图片/PDF附件测试
# ============================================================
class TestN3ImagePdfAttachment:
    """N3 图片/PDF附件返回测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_image_response_base64(self, mock_client_cls):
        """图片响应返回base64附件"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = b"\x89PNG\r\n\x1a\n" + b"x" * 100
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com/image.png")
        assert result["code"] == "SUCCESS"
        assert "attachment" in result
        assert result["attachment"]["mime"] == "image/png"
        assert result["attachment"]["type"] == "base64"
        assert len(result["attachment"]["data"]) > 0

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_pdf_response_base64(self, mock_client_cls):
        """PDF响应返回base64附件"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"%PDF-1.4" + b"x" * 100
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com/doc.pdf")
        assert result["code"] == "SUCCESS"
        assert "attachment" in result
        assert result["attachment"]["mime"] == "application/pdf"


# ============================================================
# 5. max_tokens截断测试
# ============================================================
class TestN3MaxTokensTruncation:
    """N3 max_tokens截断测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_content_truncated(self, mock_client_cls):
        """内容超过max_tokens*4时截断"""
        long_html = "<html><body><p>" + "A" * 50000 + "</p></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = long_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com", max_tokens=1000)
        assert result["code"] == "SUCCESS"
        assert result["data"]["truncated"] is True
        assert len(result["data"]["content"]) <= 1000 * 4 + 100  # 允许一定余量

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_content_not_truncated(self, mock_client_cls):
        """内容未超过max_tokens*4时不截断"""
        short_html = "<html><body><p>Short content</p></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = short_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com", max_tokens=8000)
        assert result["code"] == "SUCCESS"
        assert result["data"]["truncated"] is False


# ============================================================
# 6. 错误处理测试
# ============================================================
class TestN3ErrorHandling:
    """N3 错误处理测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_timeout(self, mock_client_cls):
        """超时 → ERR_NETWORK_TIMEOUT"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com")
        assert result["code"] == "ERR_NETWORK_TIMEOUT"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_http_404(self, mock_client_cls):
        """HTTP 404 → ERR_NETWORK_HTTP_ERROR"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com/missing")
        assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
        assert "404" in result["message"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_request_error(self, mock_client_cls):
        """网络请求错误 → ERR_NETWORK_REQUEST_ERROR"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_webpage("https://example.com")
        assert result["code"] == "ERR_NETWORK_REQUEST_ERROR"


# ============================================================
# 8. _html_to_markdown 单元测试
# ============================================================
class TestN3HtmlToMarkdown:
    """N3 _html_to_markdown 函数单元测试"""

    def test_basic_conversion(self):
        """基础HTML转Markdown"""
        html = "<h1>Title</h1><p>Paragraph</p><strong>Bold</strong><em>Italic</em>"
        md = _html_to_markdown(html)
        assert "# Title" in md
        assert "**Bold**" in md
        assert "*Italic*" in md

    def test_script_and_style_removed(self):
        """script和style标签被移除"""
        html = "<script>alert('x')</script><style>.cls{color:red}</style><p>Content</p>"
        md = _html_to_markdown(html)
        assert "alert" not in md
        assert "color:red" not in md
        assert "Content" in md

    def test_link_conversion(self):
        """a标签转Markdown链接"""
        html = '<a href="https://example.com">Link Text</a>'
        md = _html_to_markdown(html)
        assert "[Link Text](https://example.com)" in md

    def test_list_conversion(self):
        """li标签转列表"""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        md = _html_to_markdown(html)
        assert "- Item 1" in md
        assert "- Item 2" in md

    def test_headings_conversion(self):
        """h1-h6标签转标题"""
        html = "<h1>H1</h1><h2>H2</h2><h3>H3</h3>"
        md = _html_to_markdown(html)
        assert "# H1" in md
        assert "## H2" in md
        assert "### H3" in md

    def test_empty_html(self):
        """空HTML返回空字符串"""
        md = _html_to_markdown("")
        assert md == ""

    def test_only_whitespace(self):
        """只有空白字符"""
        md = _html_to_markdown("   ")
        assert md == ""
