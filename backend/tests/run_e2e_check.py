"""快速检查E2E是否可运行"""
import sys, asyncio, json, time, os
sys.path.insert(0, '.')
os.environ['AI_PROVIDER'] = 'ollama'

from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)

async def test():
    start = time.time()
    async with AsyncClient(transport=transport, timeout=60) as client:
        resp = await client.post(
            'http://test/api/v1/chat/stream/v2',
            json={
                'messages': [{'role': 'user', 'content': '你好'}],
                'stream': True
            },
        )
        elapsed = time.time() - start
        print(f'Status: {resp.status_code}, Elapsed: {elapsed:.1f}s')
        print(f'Content-Type: {resp.headers.get("content-type","")}')
        events = []
        for line in resp.text.split('\n'):
            line = line.strip()
            if line.startswith('data: '):
                try:
                    evt = json.loads(line[6:])
                    events.append(evt)
                    print(f'  SSE: type={evt.get("type","")} content={str(evt.get("content",""))[:80]}')
                except:
                    pass
        print(f'\nTotal SSE events: {len(events)}')
        return len(events) > 0

result = asyncio.run(test())
print(f'\nTest {"PASSED" if result else "FAILED"}')
sys.exit(0 if result else 1)
