#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json
import sys

API_BASE = "https://api.longcat.chat/openai/v1"
API_KEY = "ak_2yt5nN61V36y88L7t21rF48K7ID4c"
MODEL = "LongCat-Flash-Thinking"

url = f"{API_BASE}/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "1+1等于几"}],
    "stream": True
}

response = requests.post(url, headers=headers, json=data, stream=True, timeout=30)

print(f"Status: {response.status_code}")

count = 0
full_content = ""
full_reasoning = ""

for line in response.iter_lines():
    if not line:
        continue
    line_str = line.decode('utf-8') if isinstance(line, bytes) else line
    
    if line_str.startswith("data: "):
        data_str = line_str[6:]
        if data_str.strip() == "[DONE]":
            print("=== DONE ===")
            break
        
        # 打印原始数据
        if count < 3:
            print(f"=== Raw {count} ===")
            print(repr(data_str[:200]))
            print()
        
        try:
            parsed = json.loads(data_str)
            delta = parsed.get("choices", [{}])[0].get("delta", {})
            
            if count < 3:
                print(f"=== Parsed {count} ===")
                print(f"delta keys: {list(delta.keys())}")
                print(f"delta: {json.dumps(delta, ensure_ascii=False)[:200]}")
                print()
            
            content = delta.get("content", "")
            reasoning = delta.get("reasoning_content", "") or delta.get("reasoning", "")
            
            if content:
                full_content += content
            if reasoning:
                full_reasoning += reasoning
                
            count += 1
        except json.JSONDecodeError as e:
            print(f"JSON Error: {e}")
            print(f"Data: {data_str[:200]}")
            print()

print("=" * 50)
print(f"Total content: {len(full_content)} chars")
print(f"Total reasoning: {len(full_reasoning)} chars")
print(f"Content: {full_content[:100]}")
