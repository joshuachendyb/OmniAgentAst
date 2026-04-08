import sqlite3
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

# 查看最新的assistant消息
cursor.execute('''
SELECT id, session_id, role, timestamp, execution_steps
FROM chat_messages 
WHERE role = 'assistant' 
ORDER BY id DESC LIMIT 1
''')
msg = cursor.fetchone()
print(f'最新assistant消息: id={msg[0]}, session_id={msg[1]}')
print(f'timestamp: {msg[3]}')

# 解析execution_steps
if msg[4]:
    steps = json.loads(msg[4])
    print(f'\n=== Execution Steps (共{len(steps)}条) ===')
    for i, step in enumerate(steps):
        step_type = step.get('type', 'unknown')
        step_num = step.get('step', i+1)
        tool_name = step.get('tool_name', '')
        content = step.get('content', '')
        if content and len(str(content)) > 40:
            content = str(content)[:40] + '...'
        print(f'  [{i+1}] Step{step_num}: type={step_type}, tool={tool_name}, content={content}')
else:
    print('\n没有execution_steps数据')

conn.close()
