import re

with open(r'G:\OmniAgentAs-desk\backend\logs\app_2026-05-21.log', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

lines = content.split('\n')

# Find user messages - look for actual message content in test context
print('=== 用户消息（从日志中提取）===')
user_msgs = set()
for line in lines:
    # Look for actual user query sends
    if '用户消息' in line or 'send_message' in line or '消息内容' in line or 'user_input' in line:
        # Try to extract content
        m = re.search(r'["\'"]content["\'"]\s*[:=]\s*["\']([^"\']+)["\']', line)
        if m:
            msg = m.group(1)
            if len(msg) > 5 and len(msg) < 200:
                user_msgs.add(msg)

# Also search for test scenario messages
for line in lines:
    for kw in ['读取', 'PowerShell', 'HTTP', '搜索', '帮助', '你好', '计算', '翻译']:
        if kw in line and 'content' in line.lower():
            m = re.search(r'["\'"]?content["\'"]?\s*[:=]\s*["\']([^"\']+)["\']', line)
            if m:
                msg = m.group(1)
                if len(msg) > 5 and len(msg) < 200:
                    user_msgs.add(msg)
            break

print(f'找到 {len(user_msgs)} 条用户消息:')
for i, msg in enumerate(sorted(user_msgs)):
    print(f'  [{i+1}] "{msg[:80]}"')
print()

# Now find the exact mapping: user message → LLM response
print('=== 用户消息 → LLM响应 映射关系 ===')
user_message = ''
session_id = ''
count = 0
for line in lines:
    # Track user messages
    if '发送用户消息' in line or '用户输入' in line:
        m = re.search(r'["\'"]content["\'"]\s*[:=]\s*["\']([^"\']+)["\']', line)
        if m:
            user_message = m.group(1)[:60]

    # Track session
    if 'session' in line.lower() and 'ID' in line:
        m = re.search(r'[sS]ession[_ ]?[iI][dD]\s*[:=]\s*["\']?([a-f0-9-]+)["\']?', line)
        if m:
            session_id = m.group(1)[:12]

    # LLM response
    if 'LLM响应' in line:
        count += 1
        m = re.search(r'\[(.*?)\]', line)
        time_str = m.group(1) if m else '??:??:??'

        # Extract type + content
        resp_part = line.split('LLM响应')[1] if 'LLM响应' in line else ''
        
        tm = '?'
        cm = re.search(r'"type":\s*"([^"]+)"', line)
        if cm: tm = cm.group(1)
        
        ct = ''
        ct2 = re.search(r'"content":\s*"([^"]+)"', line)
        if ct2: ct = ct2.group(1)[:30]
        
        tn = ''
        tn2 = re.search(r'"tool_name":\s*"([^"]+)"', line)
        if tn2: tn = tn2.group(1)
        
        # Only print non-duplicate patterns
        if count <= 20 or (count % 100 == 0):
            print(f'  [{count:4d}][{time_str}] session={session_id[:8]}')
            print(f'    用户: "{user_message[:55]}"')
            print(f'    LLM:  type={tm:8} tool={tn:12} content="{ct}"')
            print()
        
        if count >= 1870:
            break

print(f'=== 总计 LLM 响应行: {count} ===')
