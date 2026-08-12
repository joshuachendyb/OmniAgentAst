"""直接验证 sensenova API 是否正常 — 小欧 2026-07-09"""
import httpx, asyncio, json, sys, time
import pytest

API_BASE = "https://token.sensenova.cn/v1"
API_KEY = "sk-BW2lJhKdYAdBWVI3iEHQMvERUPsCTwv7"
MODEL = "deepseek-v4-flash"


@pytest.mark.skip(reason="手动运行，依赖真实API连通性")
@pytest.mark.asyncio
async def test_streaming():
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "请回复 'Hello, I am working!'"}],
        "stream": True,
        "max_tokens": 100,
    }
    print(f"[{time.strftime('%H:%M:%S')}] 发起流式请求...")
    t0 = time.time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=30)) as client:
        try:
            async with client.stream("POST", f"{API_BASE}/chat/completions", json=body, headers=headers) as resp:
                print(f"    HTTP 状态码: {resp.status_code}")
                if resp.status_code != 200:
                    text = await resp.aread()
                    print(f"    错误体: {text.decode('utf-8', errors='replace')[:500]}")
                    return False
                full = ""
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        d = line[6:].strip()
                        if d == "[DONE]":
                            break
                        try:
                            js = json.loads(d)
                            c = js.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if c:
                                full += c
                        except json.JSONDecodeError:
                            pass
                elapsed = time.time() - t0
                print(f"    耗时: {elapsed:.1f}s")
                print(f"    内容({len(full)}字符): {full[:200]}")
                return len(full) > 0
        except Exception as e:
            print(f"    异常: {type(e).__name__}: {e}")
            return False

@pytest.mark.skip(reason="手动运行，依赖真实API连通性")
@pytest.mark.asyncio
async def test_non_streaming():
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "请回复 'Hello, I am working!'"}],
        "max_tokens": 100,
    }
    print(f"[{time.strftime('%H:%M:%S')}] 发起非流式请求...")
    t0 = time.time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=30)) as client:
        try:
            resp = await client.post(f"{API_BASE}/chat/completions", json=body, headers=headers)
            print(f"    HTTP 状态码: {resp.status_code}")
            if resp.status_code != 200:
                print(f"    错误体: {resp.text[:500]}")
                return False
            js = resp.json()
            content = js.get("choices", [{}])[0].get("message", {}).get("content", "")
            elapsed = time.time() - t0
            print(f"    耗时: {elapsed:.1f}s")
            print(f"    内容({len(content)}字符): {content[:200]}")
            return len(content) > 0
        except Exception as e:
            print(f"    异常: {type(e).__name__}: {e}")
            return False

async def main():
    print(f"=== sensenova API 连通性测试 ===")
    print(f"  API: {API_BASE}")
    print(f"  Model: {MODEL}")
    print()
    ok1 = await test_non_streaming()
    print()
    ok2 = await test_streaming()
    print()
    print(f"非流式: {'✓ 通过' if ok1 else '✗ 失败'}")
    print(f"流式:   {'✓ 通过' if ok2 else '✗ 失败'}")
    return 0 if ok2 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
