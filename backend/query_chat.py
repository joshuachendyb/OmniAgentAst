import sqlite3
conn = sqlite3.connect('chat_app.db')
cursor = conn.cursor()

# 查看表结构
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', cursor.fetchall())

# 查看messages表结构
cursor.execute('PRAGMA table_info(messages)')
print('\nMessages columns:', cursor.fetchall())

# 查询最近的聊天记录
cursor.execute("SELECT id, session_id, created_at, role, content FROM messages ORDER BY created_at DESC LIMIT 10")
print('\nRecent messages:')
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Session: {row[1]}, Time: {row[2]}, Role: {row[3]}, Content: {row[4][:100]}...")

conn.close()