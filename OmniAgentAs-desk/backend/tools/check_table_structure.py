import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

# 查看chat_sessions表结构
print("=== chat_sessions表结构 ===")
cursor.execute("PRAGMA table_info(chat_sessions)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]:20} | {col[2]:15} | {col[3]:10} | {col[4]}")

print("\n=== chat_sessions表数据 ===")
cursor.execute("SELECT * FROM chat_sessions WHERE title LIKE '123%'")
rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row[0]}")
    print(f"Title: {row[1]}")
    print(f"Created_at: {row[2]}")
    print(f"Updated_at: {row[3]}")
    print(f"Message_count: {row[4]}")
    print(f"Is_deleted: {row[5]}")

print("\n=== 检查是否有新字段 ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'")
print("表名:", cursor.fetchone()[0])

cursor.execute("PRAGMA table_info(chat_sessions)")
column_names = [col[1] for col in cursor.fetchall()]
print("现有字段:", column_names)

# 检查是否有title_locked等字段
new_fields = ['title_locked', 'title_updated_at', 'version']
for field in new_fields:
    exists = field in column_names
    print(f"{field}: {'存在' if exists else '不存在'}")

conn.close()