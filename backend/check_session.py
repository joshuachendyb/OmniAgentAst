import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 找一个session，查看完整的消息列表
session_id = '854edd1d-83a7-45b7-a15b-5f92d0b1c179'

print(f"=== Session: {session_id} ===")

# 查看该session的所有消息
c.execute("""
    SELECT id, role, length(execution_steps) as steps_len, length(content) as content_len
    FROM chat_messages 
    WHERE session_id = ?
    ORDER BY id ASC
""", (session_id,))

for row in c.fetchall():
    print(f"id={row[0]}, role={row[1]}, steps_len={row[2]}, content_len={row[3]}")

# 查看message_count
c.execute("SELECT id, message_count FROM chat_sessions WHERE id = ?", (session_id,))
session = c.fetchone()
if session:
    print(f"\nSession message_count: {session[1]}")

conn.close()
