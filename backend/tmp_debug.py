import asyncio, httpx, json
from httpx._transports.asgi import ASGITransport
from app.main import app

async def debug_call():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create session first
        r1 = await client.post("/api/v1/sessions", json={"title": "debug"})
        sid = r1.json()["session_id"]
        print(f"Session: {sid}")
        
        # Send message
        async with client.stream("POST", f"/api/v1/chat/stream/{sid}", json={
            "message": "查看 README.md 文件内容",
            "agent_type": "file"
        }) as resp:
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        evt = json.loads(line[6:])
                        events.append(evt)
                    except:
                        pass
            print(f"Events: {[e.get('type') for e in events]}")
            for e in events:
                if e.get("type") == "error":
                    print(f"ERROR: {e.get('error_type')}: {e.get('error_message')}")

asyncio.run(debug_call())
