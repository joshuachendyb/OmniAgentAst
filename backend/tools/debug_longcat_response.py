#!/usr/bin/env python3
import requests
import json

API_BASE = "https://api.longcat.chat/openai/v1"
API_KEY = "ak_2yt5nN61V36y88L7t21rF48K7ID4c"
MODEL = "LongCat-Flash-Thinking-2601"

url = f"{API_BASE}/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Test 1: response_format
print("Test 1: response_format")
data = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Hello"}],
    "response_format": {
        "type": "json_object",
        "json_schema": {
            "type": "object",
            "properties": {
                "response": {"type": "string"}
            }
        }
    },
    "stream": False
}

response = requests.post(url, headers=headers, json=data, timeout=30)
print(f"Status: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"Raw text: {response.text[:500]}")

# Test 2: tools
print("\n\nTest 2: tools")
data2 = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Hello"}],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "test",
                "description": "Test function",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ],
    "stream": False
}

response2 = requests.post(url, headers=headers, json=data2, timeout=30)
print(f"Status: {response2.status_code}")
print(f"Headers: {dict(response2.headers)}")
print(f"Raw text: {response2.text[:500]}")
