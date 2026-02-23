"""
测试 OpenCode API 对不同模型的访问
"""

import httpx
import asyncio
import json

# OpenCode API 配置
API_KEY = "sk-6rMee9Ez89iRCEvDayPq2hdTrMGKyPesy5K88uZKVAqOrc7tg6sVqRI5T1pP2LXb"
API_BASE = "https://opencode.ai/zen/v1"

# 要测试的模型列表
MODELS_TO_TEST = [
    "minimax-m2.5-free",
    "GLM-5 free",  # 带空格的正确名称
    "glm-5-free",   # 之前错误的名称
    "kimi-k2.5-free",  # 默认的模型
]


async def test_model(model: str):
    """测试单个模型"""
    print(f"\n{'='*60}")
    print(f"测试模型: {model}")
    print('='*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "你好"}]
                }
            )
            
            print(f"状态码: {response.status_code}")
            print(f"响应内容: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"✅ 成功! 响应: {content[:100]}...")
                return True
            else:
                print(f"❌ 失败!")
                return False
                
        except Exception as e:
            print(f"❌ 异常: {e}")
            return False


async def list_models():
    """列出可用的模型"""
    print(f"\n{'='*60}")
    print("获取可用模型列表")
    print('='*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{API_BASE}/models",
                headers={"Authorization": f"Bearer {API_KEY}"}
            )
            
            print(f"状态码: {response.status_code}")
            print(f"响应内容: {response.text[:1000]}")
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                print(f"\n可用模型 ({len(models)}个):")
                for m in models:
                    print(f"  - {m.get('id')}")
                    
        except Exception as e:
            print(f"❌ 异常: {e}")


async def main():
    # 先列出可用模型
    await list_models()
    
    # 测试每个模型
    print("\n\n" + "="*60)
    print("逐个测试模型")
    print("="*60)
    
    for model in MODELS_TO_TEST:
        await test_model(model)
        await asyncio.sleep(1)  # 避免请求过快


if __name__ == "__main__":
    asyncio.run(main())
