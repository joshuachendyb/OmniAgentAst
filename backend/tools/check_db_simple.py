import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Tables in database:")
for table in tables:
    print(f"  - {table[0]}")

# 查询会话数量
cursor.execute("SELECT COUNT(*) FROM chat_sessions")
session_count = cursor.fetchone()[0]
print(f"Sessions: {session_count}")

# 查询消息数量
cursor.execute("SELECT COUNT(*) FROM chat_messages")
message_count = cursor.fetchone()[0]
print(f"Messages: {message_count}")

conn.close()