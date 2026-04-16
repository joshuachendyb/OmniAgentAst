import sqlite3
import json
from pathlib import Path

db_path = Path.home() / ".omniagent" / "chat_history.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

msg_id = 510

cur.execute("SELECT execution_steps, timestamp FROM chat_messages WHERE id = ?", (msg_id,))
result = cur.fetchone()
steps = json.loads(result[0])

print("=== msg_id=510 的步骤详情 ===\n")

for i, step in enumerate(steps):
    step_type = step.get('type')
    print(f"[{i}] type={step_type}")
    
    if step_type == 'start':
        print(f"    user_message: {step.get('user_message', 'N/A')}")
        print(f"    timestamp: {step.get('timestamp')}")
        print(f"    task_id: {step.get('task_id', 'N/A')}")
    
    elif step_type == 'thought':
        print(f"    tool_name: {step.get('tool_name')}")
        print(f"    tool_params: {step.get('tool_params')}")
    
    elif step_type == 'action_tool':
        print(f"    tool_name: {step.get('tool_name')}")
        print(f"    execution_status: {step.get('execution_status')}")
        exec_result = step.get('execution_result')
        if exec_result:
            print(f"    execution_result keys: {list(exec_result.keys())}")
            if 'entries' in exec_result:
                print(f"    execution_result.entries 数量: {len(exec_result.get('entries', []))}")
            if 'content' in exec_result:
                content = exec_result.get('content', '')
                print(f"    execution_result.content 长度: {len(content)}")
        print(f"    execution_time_ms: {step.get('execution_time_ms')}")
    
    elif step_type == 'final':
        print(f"    content: {step.get('content', 'N/A')[:200]}...")
        print(f"    response: {step.get('response', 'N/A')[:200]}...")
    
    print()

conn.close()
