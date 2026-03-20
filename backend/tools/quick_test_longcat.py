#!/usr/bin/env python3
"""快速测试 LongCat Structured Outputs 支持"""
import requests
import json

API_BASE = "https://api.longcat.chat/openai/v1"
API_KEY = "ak_2yt5nN61V36y88L7t21rF48K7ID4c"
MODEL = "LongCat-Flash-Thinking-2601"

def test_response_format():
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    schema = {
        "type": "json_object",
        "json_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "action_tool": {"type": "string"},
                "params": {"type": "object"}
            },
            "required": ["thought", "action_tool", "params"]
        }
    }
    
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Hello, respond with JSON"}],
        "response_format": schema,
        "stream": False
    }
    
    print("Testing response_format...")
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Result keys: {list(result.keys())}")
            choices = result.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                print(f"Message keys: {list(message.keys())}")
                content = message.get("content", "")
                print(f"Content length: {len(content)}")
                print(f"Content preview: {content[:200]}")
                try:
                    parsed = json.loads(content)
                    print("JSON parse SUCCESS!")
                    return True
                except Exception as e:
                    print(f"JSON parse FAILED: {e}")
                    return False
        else:
            print(f"Error: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_tools():
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "列出目录内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dir_path": {"type": "string", "description": "目录路径"}
                    },
                    "required": ["dir_path"]
                }
            }
        }
    ]
    
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "查看D盘根目录"}],
        "tools": tools,
        "stream": False
    }
    
    print("\n测试 LongCat tools/function_calling...")
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            choices = result.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    print(f"✅ 支持 Function Calling!")
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        print(f"  函数名: {func.get('name')}")
                        print(f"  参数: {func.get('arguments')}")
                    return True
                else:
                    content = message.get("content", "")
                    print(f"不支持或未调用工具，内容: {content[:200]}")
                    return False
        else:
            print(f"错误: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"请求错误: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("LongCat Structured Outputs Support Test")
    print("=" * 60)
    
    result1 = test_response_format()
    result2 = test_tools()
    
    print("\n" + "=" * 60)
    print("Result:")
    print(f"  response_format: {'YES' if result1 else 'NO'}")
    print(f"  tools/function:  {'YES' if result2 else 'NO'}")
    print("=" * 60)
