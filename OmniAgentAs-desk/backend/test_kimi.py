"""
测试 OpenCode API - Kimi K2.5 Free
"""

import httpx
import asyncio

API_KEY = "sk-6rMee9Ez89iRCEvDayPq2hdTrMGKyPesy5K88uZKVAqOrc7tg6sVqRI5T1pP2LXb"
API_BASE = "https://opencode.ai/zen/v1"

MODELS = [
    "kimi-k2.5-free",
    "glm-5-free",
    "minimax-m2.5-free",
]

async def test_model(model: str):
    print(f"\n=== Testing: {model} ===")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Hi"}]
                }
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:300]}")
            
            if response.status_code == 200:
                print("SUCCESS!")
            else:
                print("FAILED!")
        except Exception as e:
            print(f"Error: {e}")

async def main():
    for m in MODELS:
        await test_model(m)
        await asyncio.sleep(0.5)

asyncio.run(main())
