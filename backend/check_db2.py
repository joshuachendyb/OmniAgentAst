import sqlite3

db_path = r"C:\Users\40968\.omniagent\chat_history.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 模拟前端调用: page=1, page_size=1, is_valid=true
cursor.execute(
    '''SELECT id, title, created_at, updated_at, message_count, is_valid
       FROM chat_sessions 
       WHERE is_deleted = FALSE AND is_valid = ?
        ORDER BY updated_at DESC, created_at DESC
       LIMIT ? OFFSET ?''',
    (1, 1, 0)
)
rows = cursor.fetchall()
print(f"查询结果 (page=1, page_size=1, is_valid=true):")
print(f"返回记录数: {len(rows)}")
for r in rows:
    print(f"  id={r['id']}, title={r['title']}, messages={r['message_count']}, is_valid={r['is_valid']}")

# 获取总数
cursor.execute("SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = FALSE AND is_valid = ?", (1,))
total = cursor.fetchone()[0]
print(f"\n总会话数(is_valid=1, 未删除): {total}")

# 检查所有会话的 is_valid 和 is_deleted 状态
cursor.execute("SELECT id, title, is_valid, is_deleted, message_count FROM chat_sessions ORDER BY updated_at DESC")
all_rows = cursor.fetchall()
print(f"\n所有会话状态:")
for r in all_rows:
    print(f"  id={r['id'][:8]}..., title={r['title']}, is_valid={r['is_valid']}, deleted={r['is_deleted']}, messages={r['message_count']}")

conn.close()
