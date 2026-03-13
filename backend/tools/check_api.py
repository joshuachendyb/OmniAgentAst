#!/usr/bin/env python3
import requests
import json

url = 'https://api.longcat.chat/openai/v1/chat/completions'
headers = {'Authorization': 'Bearer ak_2yt5nN61V36y88L7t21rF48K7ID4c', 'Content-Type': 'application/json'}
data = {'model': 'LongCat-Flash-Thinking', 'messages': [{'role': 'user', 'content': 'hi'}], 'stream': True}

r = requests.post(url, headers=headers, json=data, timeout=30, stream=True)

for i, line in enumerate(r.iter_lines()):
    if line:
        s = line.decode('utf-8', errors='replace')
        if s.startswith('data: '):
            raw = s[6:]
            obj = json.loads(raw)
            delta = obj['choices'][0]['delta']
            print(f'Line {i} - delta keys: {list(delta.keys())}')
            print(f'  delta: {json.dumps(delta, ensure_ascii=False)[:120]}')
    if i > 5:
        break
