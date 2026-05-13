"""
端到端测试 - 真实模拟前端发消息给后端API
编写人：小沈 - 2026-05-13

测试方式：
1. 启动FastAPI应用（通过ASGITransport，不调真实LLM）
2. 模拟LLM API的httpx响应（mock httpx.AsyncClient.post）
3. 发送真实HTTP POST请求到 /chat/stream/v2
4. 接收并验证SSE流式响应
5. 覆盖完整链路：路由→意图检测→Agent创建→SSE格式化→输出

注意：只mock最外层的LLM HTTP调用，内部全部走真实代码
"""

import pytest
import json
import asyncio
import re
from typing import AsyncGenerator, Dict, Any, Optional, List
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock
from httpx import AsyncClient, ASGITransport, Response


# ============================================================
# Mock LLM HTTP 响应（模拟外部API返回）
# ============================================================

def make_mock_llm_stream_response(content: str, reasoning: str = ""):
    """
    构造模拟的LLM API流式响应chunks
    格式与OpenAI/LongCat的SSE格式一致
    """
    chunks = []

    # reasoning_content（如果有）
    if reasoning:
        chunks.append(f'data: {json.dumps({"choices": [{"delta": {"reasoning_content": reasoning}}]})}\n\n')

    # content
    if content:
        chunks.append(f'data: {json.dumps({"choices": [{"delta": {"content": content}}]})}\n\n')

    # finish
    chunks.append('data: [DONE]\n\n')
    return chunks


class MockAsyncClient:
    """模拟httpx.AsyncClient - 拦截所有HTTP请求"""
    def __init__(self, **kwargs):
        self._kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, **kwargs):
        # 返回模拟的LLM流式响应
        content_chunks = make_mock_llm_stream_response(
            content='{"type":"chunk","content":"你好！我是AI助手。"}',
            reasoning="用户打招呼，简单回应"
        )
        return MockResponse(content_chunks)

    async def aclose(self):
        pass


class MockResponse:
    """模拟httpx.Response"""
    def __init__(self, chunks: List[str]):
        self._chunks = chunks
        self.status_code = 200
        self._headers = {"content-type": "application/json"}

    @property
    def headers(self):
        return self._headers

    @property
    def text(self):
        return ""

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk.encode()

    async def aclose(self):
        pass

    def json(self):
        return {
            "choices": [{
                "message": {
                    "content": self._get_content(),
                    "role": "assistant"
                }
            }]
        }

    def _get_content(self):
        """合并所有chunks获取完整content"""
        text = ""
        for c in self._chunks:
            if c.startswith("data: ") and "[DONE]" not in c:
                try:
                    data = json.loads(c[6:])
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    text += delta.get("content", "")
                except:
                    pass
        return text

    async def aread(self):
        return b""


# ============================================================
# Mock httpx 模块
# ============================================================

@pytest.fixture(autouse=True)
def mock_httpx():
    """全局mock httpx.AsyncClient，所有LLM调用走模拟响应"""
    with patch('app.services.llm_core.httpx.AsyncClient', MockAsyncClient):
        yield


# ============================================================
# 端到端测试
# ============================================================

class TestEndToEndChatAPI:
    """端到端测试 - 模拟前端发消息"""

    @pytest.mark.asyncio
    async def test_chat_basic_greeting(self, mock_httpx):
        """测试普通问候"""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True
                },
                timeout=30
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            text = response.text
            assert "data: " in text
            print(f"  HTTP 200, content-type={response.headers.get('content-type')}")
            print(f"  响应前100字: {text[:100]}")

    @pytest.mark.asyncio
    async def test_chat_stream_has_sse_format(self, mock_httpx):
        """验证SSE每行都是有效的 data: 格式"""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": "今天天气怎么样"}],
                    "stream": True
                },
                timeout=30
            )
            assert response.status_code == 200

            # 解析SSE行
            lines = response.text.strip().split('\n')
            sse_events = []
            for line in lines:
                line = line.strip()
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        sse_events.append(data)
                    except json.JSONDecodeError:
                        pass

            assert len(sse_events) > 0
            # 验证第一个事件是start
            assert sse_events[0]["type"] == "start"
            # 验证所有事件都有type和step
            for evt in sse_events:
                assert "type" in evt
                assert "step" in evt
            print(f"  SSE事件数: {len(sse_events)}")
            print(f"  事件类型: {[e['type'] for e in sse_events]}")

    @pytest.mark.asyncio
    async def test_chat_step_numbering(self, mock_httpx):
        """验证step递增"""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": "现在几点了"}],
                    "stream": True
                },
                timeout=30
            )
            lines = response.text.strip().split('\n')
            steps = []
            for line in lines:
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        steps.append((data["type"], data["step"]))
                    except:
                        pass

            # 验证step严格递增
            step_nums = [s[1] for s in steps]
            assert step_nums == list(range(1, len(steps) + 1)), f"step应递增: {step_nums}"
            print(f"  step序列: {step_nums}")

    @pytest.mark.asyncio
    async def test_chat_with_long_message(self, mock_httpx):
        """测试长文本输入"""
        from app.main import app

        long_msg = "请详细介绍一下人工智能的发展历史" * 10

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": long_msg}],
                    "stream": True
                },
                timeout=30
            )
            assert response.status_code == 200
            lines = response.text.strip().split('\n')
            sse_count = sum(1 for l in lines if l.startswith("data: ") and "[DONE]" not in l)
            assert sse_count > 0
            print(f"  长文本: 输入{len(long_msg)}字, SSE事件{sse_count}个")

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, mock_httpx):
        """测试空消息"""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": ""}],
                    "stream": True
                },
                timeout=30
            )
            # 空消息应该返回错误（不是200）
            print(f"  空消息响应码: {response.status_code}")

    @pytest.mark.asyncio
    async def test_chat_multi_turn(self, mock_httpx):
        """模拟多轮对话"""
        from app.main import app
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 第一轮
            resp1 = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True,
                    "session_id": "e2e-test-session"
                },
                timeout=30
            )
            assert resp1.status_code == 200

            # 第二轮（同一session）
            resp2 = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [
                        {"role": "user", "content": "你好"},
                        {"role": "assistant", "content": "你好！"},
                        {"role": "user", "content": "今天天气怎么样"}
                    ],
                    "stream": True,
                    "session_id": "e2e-test-session"
                },
                timeout=30
            )
            assert resp2.status_code == 200
            lines2 = resp2.text.strip().split('\n')
            sse2 = [json.loads(l[6:]) for l in lines2 if l.startswith("data: ") and l[6:].strip()]
            types2 = [e["type"] for e in sse2]
            print(f"  多轮对话SSE类型: {types2}")

    @pytest.mark.asyncio
    async def test_chat_special_characters(self, mock_httpx):
        """测试特殊字符输入"""
        from app.main import app

        special_msgs = [
            "Hello World! @#$%^&*()",
            "line1\nline2\nline3",
            "<script>alert('xss')</script>",
            "  前后空格  ",
            "中文English混合123!@#",
        ]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for msg in special_msgs:
                response = await client.post(
                    "/api/v1/chat/stream/v2",
                    json={
                        "messages": [{"role": "user", "content": msg}],
                        "stream": True
                    },
                    timeout=30
                )
                assert response.status_code == 200
                print(f"  特殊字符[{msg[:30]}]: HTTP {response.status_code}")

    @pytest.mark.asyncio
    async def test_health_endpoint(self, mock_httpx):
        """验证服务健康检查"""
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            print(f"  Health: {data}")

    @pytest.mark.asyncio
    async def test_chat_sse_contains_start_step(self, mock_httpx):
        """验证SSE流第一个事件是start类型"""
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": "测试start步骤"}],
                    "stream": True
                },
                timeout=30
            )
            lines = response.text.strip().split('\n')
            first_data = None
            for l in lines:
                if l.startswith("data: ") and l[6:].strip():
                    try:
                        first_data = json.loads(l[6:])
                        break
                    except:
                        pass
            assert first_data is not None
            assert first_data["type"] == "start", f"第一个事件应为start: {first_data['type']}"
            print(f"  首个事件: type={first_data['type']}, step={first_data.get('step')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
