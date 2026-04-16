import sqlite3
from pathlib import Path

db_path = Path.home() / ".omniagent" / "chat_history.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

session_id = 'cf91de03-c15a-4e27-9d81-096f2dbe9585'

# 查看数据库中的表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("数据库表:", [r[0] for r in tables])

# 查询消息数量和 execution_steps 总大小
cur.execute("""
    SELECT 
        COUNT(*) as msg_count,
        SUM(LENGTH(execution_steps)) as total_steps_size
    FROM chat_messages 
    WHERE session_id = ?
""", (session_id,))

result = cur.fetchone()
print(f"\n=== 会话 cf91de03... ===")
print(f"消息数量: {result[0]}")
if result[1]:
    print(f"execution_steps 总大小: {result[1] / 1024 / 1024:.2f} MB")
else:
    print("execution_steps 总大小: 0")

# 查询每条消息的 execution_steps 大小
cur.execute("""
    SELECT id, role, LENGTH(execution_steps) as steps_size
    FROM chat_messages 
    WHERE session_id = ? AND execution_steps IS NOT NULL
    ORDER BY LENGTH(execution_steps) DESC
    LIMIT 10
""", (session_id,))

print("\n前10条最大的 execution_steps:")
for row in cur.fetchall():
    if row[2]:
        print(f"  msg_id={row[0]}, role={row[1]}, size={row[2]/1024:.2f} KB")

conn.close()
