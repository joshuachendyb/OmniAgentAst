# 端到端测试脚本 - 发送消息与流式响应
# 测试时间: 2026-02-18 17:35
# 测试人: 小新

import requests
import json
import yaml
import time

# 加载配置
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

BASE_URL = "http://localhost:8000/api/v1"

print("=" * 60)
print("端到端测试 - 发送消息与流式响应")
print("=" * 60)
print()

# 1. 健康检查
print("【测试1】健康检查")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    if response.status_code == 200:
        print(f"✅ 后端服务正常: {response.json()}")
    else:
        print(f"⚠️ 后端返回异常状态码: {response.status_code}")
except Exception as e:
    print(f"❌ 后端服务未启动: {e}")
    print("请先启动后端服务: cd backend && python -m uvicorn app.main:app --port 8000")
    exit(1)

print()

# 2. 配置验证
print("【测试2】配置验证")
try:
    response = requests.get(f"{BASE_URL}/config", timeout=5)
    if response.status_code == 200:
        config_data = response.json()
        print(f"✅ 配置获取成功")
        print(f"  - AI提供商: {config_data.get('ai_provider')}")
        print(f"  - 模型: {config_data.get('ai_model')}")
        print(f"  - API Key已配置: {config_data.get('api_key_configured')}")
    else:
        print(f"⚠️ 配置获取失败: {response.status_code}")
except Exception as e:
    print(f"❌ 配置验证失败: {e}")

print()

# 3. 创建会话
print("【测试3】创建会话")
session_id = None
try:
    response = requests.post(f"{BASE_URL}/sessions", json={"title": "测试会话"}, timeout=5)
    if response.status_code == 200:
        session_data = response.json()
        session_id = session_data.get('session_id')
        print(f"✅ 会话创建成功")
        print(f"  - Session ID: {session_id}")
        print(f"  - 标题: {session_data.get('title')}")
    else:
        print(f"⚠️ 会话创建失败: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ 会话创建失败: {e}")

print()

# 4. 发送消息（非流式）
print("【测试4】发送消息（非流式）")
if session_id:
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "messages": [{"role": "user", "content": "你好，请介绍一下自己"}],
                "temperature": 0.7
            },
            timeout=30
        )
        if response.status_code == 200:
            chat_data = response.json()
            print(f"✅ 消息发送成功")
            print(f"  - 响应类型: {chat_data.get('response_type')}")
            print(f"  - 是否有响应: {'是' if chat_data.get('response') else '否'}")
        else:
            print(f"⚠️ 消息发送失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ 消息发送失败: {e}")
else:
    print("⏭️ 跳过（会话未创建）")

print()

# 5. 流式响应测试
print("【测试5】流式响应测试")
if session_id:
    try:
        print("  正在测试SSE连接...")
        # 先发送消息获取execution_id
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "messages": [{"role": "user", "content": "你好"}],
                "temperature": 0.7,
                "stream": True
            },
            timeout=10
        )
        
        if response.status_code == 200:
            chat_data = response.json()
            execution_id = chat_data.get('execution_id')
            
            if execution_id:
                print(f"  ✅ 获取到Execution ID: {execution_id}")
                print(f"  流式响应URL: {BASE_URL}/chat/execution/{execution_id}/stream")
                print(f"  （请使用浏览器或SSE客户端测试流式响应）")
            else:
                print(f"  ⚠️ 未获取到Execution ID")
        else:
            print(f"  ⚠️ 流式消息发送失败: {response.status_code}")
    except Exception as e:
        print(f"  ❌ 流式响应测试失败: {e}")
else:
    print("  ⏭️ 跳过（会话未创建）")

print()
print("=" * 60)
print("测试完成")
print("=" * 60)
print()
print("注意: 如果后端服务未启动，请先执行:")
print("  cd backend && python -m uvicorn app.main:app --port 8000")
