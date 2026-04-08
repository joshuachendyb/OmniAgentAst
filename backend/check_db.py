import sqlite3

db_path = r"C:\Users\40968\.omniagent\chat_history.db"
print(f"数据库路径: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"\n所有表: {[t[0] for t in tables]}")

# 检查chat_sessions表
if ('chat_sessions',) in tables:
    cursor.execute("SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = 0")
    total = cursor.fetchone()[0]
    print(f"\n总会话数(未删除): {total}")
    
    cursor.execute("SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = 0 AND is_valid = 1")
    valid = cursor.fetchone()[0]
    print(f"有效会话数: {valid}")
    
    cursor.execute("SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = 0 AND is_valid = 0")
    invalid = cursor.fetchone()[0]
    print(f"无效会话数: {invalid}")
    
    cursor.execute("SELECT id, title, message_count, is_valid, is_deleted FROM chat_sessions ORDER BY updated_at DESC LIMIT 5")
    rows = cursor.fetchall()
    print(f"\n最近5条会话:")
    for r in rows:
        print(f"  id={r[0]}, title={r[1]}, messages={r[2]}, is_valid={r[3]}, deleted={r[4]}")
else:
    print("\nchat_sessions表不存在!")

conn.close()
