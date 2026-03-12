import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

session_id = 'd5c36d79-cd4e-403e-81bc-26507fc866f8'

print("=== 检查123会话的消息 ===")

# 查询消息数量
cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
count = cursor.fetchone()[0]
print(f"消息总数: {count}")

if count > 0:
    print(f"\n=== 最近的5条消息 ===")
    cursor.execute("SELECT id, role, SUBSTR(content, 1, 100), timestamp FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 5", (session_id,))
    messages = cursor.fetchall()
    for msg in messages:
        print(f"ID: {msg[0]}")
        print(f"  Role: {msg[1]}")
        print(f"  Content: {msg[2]}...")
        print(f"  Timestamp: {msg[3]}")
        print()
else:
    print("\n123会话没有任何消息记录")

print("\n=== 所有会话的消息数量 ===")
cursor.execute("""
    SELECT s.id, s.title, s.message_count, COUNT(m.id) as actual_count
    FROM chat_sessions s
    LEFT JOIN chat_messages m ON s.id = m.session_id
    WHERE s.is_deleted = FALSE
    GROUP BY s.id, s.title, s.message_count
    ORDER BY s.created_at DESC
    LIMIT 10
""")
rows = cursor.fetchall()
print("会话ID | 标题 | message_count | 实际消息数")
print("-" * 80)
for row in rows:
    print(f"{row[0][:8]}... | {row[1][:15]} | {row[2]} | {row[3]}")

conn.close()