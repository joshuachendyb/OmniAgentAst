import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

print("=== 检查所有会话的消息情况 ===")

cursor.execute("""
    SELECT 
        s.id, 
        s.title, 
        s.message_count as db_count,
        COUNT(m.id) as actual_count,
        s.created_at
    FROM chat_sessions s
    LEFT JOIN chat_messages m ON s.id = m.session_id
    WHERE s.is_deleted = FALSE
    GROUP BY s.id, s.title, s.message_count, s.created_at
    ORDER BY s.created_at DESC
    LIMIT 20
""")

rows = cursor.fetchall()
print(f"{'会话ID':12} | {'标题':20} | {'DB计数':8} | {'实际计数':8} | {'创建时间':25}")
print("-" * 85)

for row in rows:
    print(f"{str(row[0])[:8]+'...' if row[0] else 'None':<12} | {str(row[1])[:20]:<20} | {row[2]:<8} | {row[3]:<8} | {str(row[4])[:23]+'...' if row[4] else 'None':<25}")

print("\n=== 查找有消息的会话 ===")

cursor.execute("""
    SELECT session_id, COUNT(*) as count
    FROM chat_messages
    GROUP BY session_id
    ORDER BY count DESC
    LIMIT 10
""")

msg_rows = cursor.fetchall()
for row in msg_rows:
    print(f"会话ID: {row[0][:12]}... | 消息数: {row[1]}")

conn.close()