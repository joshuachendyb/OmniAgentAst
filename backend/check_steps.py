import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查看消息761的execution_steps
cursor.execute('SELECT id, role, content, execution_steps FROM chat_messages WHERE id = 761')
row = cursor.fetchone()
if row:
    print(f"id={row['id']}, role={row['role']}")
    print(f"content长度={len(row['content']) if row['content'] else 0}")
    
    steps = json.loads(row['execution_steps']) if row['execution_steps'] else []
    print(f"execution_steps数量={len(steps)}")
    
    print("\n前3个step:")
    for i, s in enumerate(steps[:3]):
        t = s.get("type", "")
        ts = s.get("timestamp", "")
        print(f"  {i}: type={t}, timestamp={ts}")
    
    print("\n最后3个step:")
    for i, s in enumerate(steps[-3:]):
        idx = len(steps) - 3 + i
        t = s.get("type", "")
        print(f"  {idx}: type={t}")
else:
    print("消息761不存在")

conn.close()
