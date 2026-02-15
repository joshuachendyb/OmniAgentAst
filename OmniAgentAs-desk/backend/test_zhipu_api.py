"""
测试智谱API配置
"""
import asyncio
import httpx

async def test_zhipu_api():
    """测试智谱API配置"""
    api_key = "5790cd6d8981471da11dda7523da11ad.VT36xKqyrpQKVR8C"
    api_base = "https://open.bigmodel.cn/api/paas/v4"
    model = "glm-4.7-flash"
    
    print("="*60)
    print("测试智谱API配置")
    print("="*60)
    print(f"API Key: {api_key[:10]}...{api_key[-10:]}")
    print(f"Model: {model}")
    print(f"API Base: {api_base}")
    print()
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            print("发送验证请求...")
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "你好"}]
                }
            )
            
            print(f"状态码: {response.status_code}")
            print(f"响应内容前500字符: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"\n✅ API Key有效！")
                print(f"AI回复: {content[:100]}")
                return True
            elif response.status_code == 401:
                print(f"\n❌ API Key无效或已过期")
                return False
            elif response.status_code == 429:
                print(f"\n⚠️ 速率限制，请稍后再试")
                return False
            else:
                print(f"\n❌ 其他错误: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"\n❌ 请求异常: {type(e).__name__}: {e}")
            return False

if __name__ == "__main__":
    result = asyncio.run(test_zhipu_api())
    print("\n" + "="*60)
    if result:
        print("结果: API配置正确")
    else:
        print("结果: API配置有问题")
    print("="*60)
