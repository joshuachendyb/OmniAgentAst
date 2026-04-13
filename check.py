import sqlite3
import json

db_path = r'C:\Users\40968\.omniagent\chat_history.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 找数据库最新的一条消息
cursor.execute("""
    SELECT m.id, m.session_id, m.role, m.timestamp
    FROM chat_messages m
    JOIN chat_sessions s ON m.session_id = s.id
    WHERE s.is_deleted = FALSE
    ORDER BY m.timestamp DESC
    LIMIT 1
""")
last_msg = cursor.fetchone()

print(f"最新消息: {last_msg[0]}")
print(f"会话ID: {last_msg[1]}")
print(f"角色: {last_msg[2]}")
print(f"时间: {last_msg[3]}")

# 会话标题
cursor.execute("SELECT title FROM chat_sessions WHERE id = ?", (last_msg[1],))
title = cursor.fetchone()[0]
print(f"会话标题: {title}")

# 该会话有多少条消息
cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (last_msg[1],))
count = cursor.fetchone()[0]
print(f"消息数: {count}")

# 最后一条assistant消息的steps
cursor.execute("""
    SELECT id, execution_steps
    FROM chat_messages
    WHERE session_id = ? AND role = 'assistant'
    ORDER BY timestamp DESC
    LIMIT 1
""", (last_msg[1],))
assistant = cursor.fetchone()

print(f"\n最后assistant消息ID: {assistant[0]}")
if assistant[1]:
    steps = json.loads(assistant[1]) if isinstance(assistant[1], str) else assistant[1]
    print(f"Steps数量: {len(steps)}")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s.get('type')}")

conn.close()