"""
精确测试search_web工具，验证到底是DuckDuckGo还是Bing的问题
"""
import sys, json, asyncio, httpx
sys.path.insert(0, '.')

async def test():
    # 1. 直接调DuckDuckGo API（完全模拟工具代码）
    print("=== 1. DuckDuckGo精确调用 ===")
    query = "AI trends 2025"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=5.0), follow_redirects=True) as client:
            resp = await client.get("https://api.duckduckgo.com/", params=params, headers=headers)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                topics = data.get("RelatedTopics", [])
                print(f"AbstractText: {(abstract[:80] + '...') if abstract else '(empty)'}")
                print(f"RelatedTopics: {len(topics)} items")
                if topics and isinstance(topics[0], dict):
                    print(f"First topic keys: {list(topics[0].keys())}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # 2. 调search_web看结果
    print()
    print("=== 2. search_web工具调用 ===")
    from app.services.tools.network.network_tools import search_web
    r = await search_web(query, num_results=5)
    d = r.get("data", {})
    print(f"code={r['code']} engine={d.get('engine','?')} total={d.get('total',0)}")
    if d.get("results"):
        for res in d["results"][:2]:
            print(f"  {res.get('title','?')[:60]}")
    else:
        print("  No results")

    # 3. 测试DuckDuckGo不同query
    print()
    print("=== 3. DuckDuckGo用中文query ===")
    params2 = {"q": "今天天气", "format": "json", "no_html": 1, "skip_disambig": 1}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        resp2 = await client.get("https://api.duckduckgo.com/", params=params2, headers=headers)
        print(f"Status: {resp2.status_code}")
        data2 = resp2.json()
        print(f"Abstract: {(data2.get('AbstractText','')[:60]) or '(empty)'}")
        print(f"Topics: {len(data2.get('RelatedTopics',[]))}")

    # 4. 测试Bing不带额外参数
    print()
    print("=== 4. Bing ===（看看是否5秒超时）")
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp3 = await client.get("https://www.bing.com/search?q=test", headers=headers)
            print(f"Bing Status: {resp3.status_code}")
            html = resp3.text
            has_algo = "b_algo" in html
            print(f"Has b_algo: {has_algo}")
    except Exception as e:
        print(f"Bing Error: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test())
