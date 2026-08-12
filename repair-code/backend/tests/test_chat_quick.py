"""快速测试后端chat接口 — 小欧 2026-07-09"""
import asyncio, json, httpx

async def main():
    url = "http://127.0.0.1:8000/api/v1/chat"
    payload = {"messages": [{"role": "user", "content": "你好，请用一句话回复我"}], "stream": False}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, json=payload)
        print(f"POST /api/v1/chat => {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"response_text: {(d.get('response_text') or '')[:300]}")
            print(f"has_error: {d.get('has_error')}")
            print(f"total_steps: {d.get('total_steps')}")
        else:
            print(r.text[:500])

asyncio.run(main())
