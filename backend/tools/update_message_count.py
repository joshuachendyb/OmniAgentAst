import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

session_id = 'd5c36d79-cd4e-403e-81bc-26507fc866f8'

# 查询所有消息（包括系统消息）
cursor.execute("SELECT id, role, content, timestamp FROM chat_messages WHERE session_id = ?", (session_id,))
messages = cursor.fetchall()

print(f"=== 123会话的所有消息（共{len(messages)}条）===")
for msg in messages:
    print(f"\nID: {msg[0]}")
    print(f"Role: {msg[1]}")
    print(f"Content: {msg[2]}")
    print(f"Timestamp: {msg[3]}")

# 手动更新message_count
cursor.execute("UPDATE chat_sessions SET message_count = ? WHERE id = ?", (len(messages), session_id))
conn.commit()

print(f"\n=== 更新会话的message_count ===")
cursor.execute("SELECT message_count FROM chat_sessions WHERE id = ?", (session_id,))
new_count = cursor.fetchone()[0]
print(f"新message_count: {new_count}")

conn.close()