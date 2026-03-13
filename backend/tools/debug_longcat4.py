#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests

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
for line in response.iter_lines():
    if not line:
        continue
    line_str = line.decode('utf-8') if isinstance(line, bytes) else line
    print(f"Line {count}: {line_str[:300]}")
    count += 1
    if count >= 5:
        break
