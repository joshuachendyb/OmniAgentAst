"""快速调试：看看Chat请求到底发生了什么"""
import sys, asyncio, json, time
sys.path.insert(0, '.')
import httpx

CHAT_URL = "http://127.0.0.1:8000/api/v1/chat/stream/v2"

async def debug():
    print(f"[{time.strftime('%H:%M:%S')}] 发送请求: 获取当前时间")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            payload = {"messages": [{"role": "user", "content": "现在几点钟了？"}], "stream": True}
            print(f"[{time.strftime('%H:%M:%S')}] 等待响应...")
            resp = await client.post(CHAT_URL, json=payload)
            elapsed = time.time() - start
            print(f"[{time.strftime('%H:%M:%S')}] 收到响应: HTTP {resp.status_code}, 耗时{elapsed:.1f}s")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  Content-Length: {len(resp.text)}")
            events = []
            for line in resp.text.split("\n"):
                if line.startswith("data: "):
                    try:
                        evt = json.loads(line[6:])
                        events.append(evt)
                        et = evt.get("type","")
                        if et in ("start","thought","action_tool","observation","final","error"):
                            print(f"  [{et}] {str(evt.get('content','') or evt.get('tool_name','') or evt.get('message',''))[:120]}")
                    except: pass
            print(f"\n总计事件: {len(events)}")
    except httpx.TimeoutException as e:
        print(f"[{time.strftime('%H:%M:%S')}] 超时: {e}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 异常: {type(e).__name__}: {e}")

start = time.time()
asyncio.run(debug())
