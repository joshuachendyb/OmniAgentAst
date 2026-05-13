"""调试脚本 - 查看e2e测试实际响应内容"""
import sys, json, asyncio
sys.path.insert(0, '.')
import httpx
from unittest.mock import patch
from app.main import app
from httpx import AsyncClient, ASGITransport

async def mock_post(self, url, **kwargs):
    class MockResp:
        def __init__(self):
            self.status_code = 200
            self._headers = {"content-type": "application/json; charset=utf-8"}
            self._chunks = [
                'data: {"choices": [{"delta": {"reasoning_content": "思考过程"}}]}\n\n',
                'data: {"choices": [{"delta": {"content": "测试回答"}}]}\n\n',
                'data: [DONE]\n\n'
            ]
        @property
        def headers(self):
            return self._headers
        async def __aiter__(self):
            for c in self._chunks:
                yield c.encode()
    return MockResp()

async def test():
    with patch.object(httpx.AsyncClient, "post", mock_post):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/chat/stream/v2", json={
                "messages": [{"role": "user", "content": "你好"}],
                "stream": True
            }, timeout=30)

            print(f"Status: {resp.status_code}")
            print(f"Content-Type: {resp.headers.get('content-type', '')}")
            text = resp.text
            print(f"Total length: {len(text)}")
            print()
            
            lines = text.strip().split("\n")
            events = []
            for l in lines:
                if l.startswith("data: "):
                    raw = l[6:]
                    try:
                        d = json.loads(raw)
                        events.append(d)
                    except:
                        print(f"  PARSE ERROR: {raw[:100]}")
            
            print(f"SSE events: {len(events)}")
            print()
            for e in events:
                t = e.get("type", "?")
                s = e.get("step", "?")
                c = str(e.get("content", ""))[:80]
                err = e.get("error", "")
                em = e.get("error_message", "")
                print(f"  step={s} type={t} content={c[:60]}")
                if err:
                    print(f"    error={err}")
                if em:
                    print(f"    error_message={em}")

asyncio.run(test())
