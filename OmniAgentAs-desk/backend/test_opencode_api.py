"""
测试OpenCode Zen API地址
"""
import httpx
import asyncio

# 测试两个可能的API地址
API_ENDPOINTS = [
    "https://opencode.ai/zen/v1/chat/completions",
    "https://opencode.ai/zen/v1/messages",
    "https://api.opencode.ai/v1/chat/completions",
]

async def test_endpoint(url: str):
    """测试单个API端点"""
    print(f"\n{'='*60}")
    print(f"测试: {url}")
    print('='*60)
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 尝试不带认证的GET请求
            print("1. 测试GET请求...")
            response = await client.get(url)
            print(f"   状态码: {response.status_code}")
            print(f"   响应内容前200字符: {response.text[:200]}")
            
            # 尝试POST请求（模拟对话）
            print("\n2. 测试POST请求...")
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "model": "kimi-k2.5-free",
                    "messages": [{"role": "user", "content": "你好"}]
                }
            )
            print(f"   状态码: {response.status_code}")
            print(f"   响应内容前500字符: {response.text[:500]}")
            
            # 检查是否可以解析JSON
            try:
                data = response.json()
                print(f"   JSON解析成功!")
                if "choices" in data:
                    print(f"   ✅ 看起来是正确的API端点！")
                    return True
            except:
                print(f"   JSON解析失败")
                
    except httpx.TimeoutException:
        print(f"   ❌ 请求超时")
    except Exception as e:
        print(f"   ❌ 错误: {type(e).__name__}: {e}")
    
    return False

async def main():
    print("OpenCode Zen API端点测试")
    print("="*60)
    
    results = []
    for endpoint in API_ENDPOINTS:
        is_valid = await test_endpoint(endpoint)
        results.append((endpoint, is_valid))
    
    print("\n" + "="*60)
    print("测试结果汇总:")
    print("="*60)
    for endpoint, is_valid in results:
        status = "✅ 可用" if is_valid else "❌ 不可用"
        print(f"{status}: {endpoint}")
    
    # 找出可用的端点
    valid_endpoints = [ep for ep, valid in results if valid]
    if valid_endpoints:
        print(f"\n✅ 推荐使用: {valid_endpoints[0]}")
    else:
        print("\n❌ 所有端点都不可用，可能需要:")
        print("   - API Key认证")
        print("   - 不同的请求格式")
        print("   - 查看OpenCode官方文档")

if __name__ == "__main__":
    asyncio.run(main())
