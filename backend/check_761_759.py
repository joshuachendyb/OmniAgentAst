import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 查看761和759的详细信息
for msg_id in [761, 759]:
    c.execute("SELECT id, session_id, role, content, execution_steps, timestamp FROM chat_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    if row:
        print(f"=== 消息 {msg_id} ===")
        print(f"session_id: {row['session_id']}")
        print(f"role: {row['role']}")
        print(f"timestamp: {row['timestamp']}")
        print(f"content长度: {len(row['content']) if row['content'] else 0}")
        if row['execution_steps']:
            steps = json.loads(row['execution_steps'])
            print(f"steps数量: {len(steps)}")
            print("steps类型列表:")
            for i, s in enumerate(steps):
                t = s.get('type', 'unknown')
                ts = s.get('timestamp', '')
                print(f"  {i}: type={t}, timestamp={ts}")
        else:
            print("execution_steps: None 或 空")
        print()

# 查看session的message_count
session_id = '854edd1d-83a7-45b7-a15b-5f92d0b1c179'
c.execute("SELECT id, message_count FROM chat_sessions WHERE id = ?", (session_id,))
row = c.fetchone()
if row:
    print(f"Session message_count: {row[1]}")

conn.close()
