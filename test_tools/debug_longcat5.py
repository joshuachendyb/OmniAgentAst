#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json

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

full_content = ""
full_reasoning = ""

for line in response.iter_lines():
    if not line:
        continue
    
    # 使用 latin-1 编码处理字节
    if isinstance(line, bytes):
        line_str = line.decode('utf-8', errors='replace')
    else:
        line_str = line
    
    if line_str.startswith("data: "):
        data_str = line_str[6:]
        if data_str.strip() == "[DONE]":
            break
        
        try:
            parsed = json.loads(data_str)
            delta = parsed.get("choices", [{}])[0].get("delta", {})
            
            content = delta.get("content", "") or ""
            reasoning = delta.get("reasoning_content", "") or delta.get("reasoning", "") or ""
            
            if content:
                full_content += content
            if reasoning:
                full_reasoning += reasoning
                
        except Exception as e:
            print(f"Error: {e}")

print(f"Content: {len(full_content)} chars")
print(f"Reasoning: {len(full_reasoning)} chars")
print(f"Content text: {repr(full_content)}")
print(f"Reasoning text: {repr(full_reasoning)}")
