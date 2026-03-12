import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

print("=== 检查后端日志中的会话 ===")

# 检查后端日志中最近保存消息的会话
session_id = '07a409f7-ee38-43b1-938c-f44a4766e2a7'

cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
session = cursor.fetchone()

if session:
    print(f"\n会话ID: {session[0]}")
    print(f"标题: {session[1]}")
    print(f"Created: {session[2]}")
    print(f"Updated: {session[3]}")
    print(f"Message_count: {session[4]}")
    
    # 查询这个会话的所有消息
    cursor.execute("SELECT id, role, SUBSTR(content, 1, 100), timestamp FROM chat_messages WHERE session_id = ? ORDER BY id", (session_id,))
    messages = cursor.fetchall()
    
    print(f"\n实际消息数: {len(messages)}")
    print("\n消息列表:")
    for i, msg in enumerate(messages, 1):
        print(f"{i}. [{msg[1]}] {msg[2]}... ({msg[3][:19]})")
else:
    print(f"会话 {session_id} 不存在")

# 检查123会话和07a409f7会话的关系
print("\n=== 对比两个会话 ===")

cursor.execute("""
    SELECT id, title, message_count, created_at
    FROM chat_sessions
    WHERE id IN ('d5c36d79-cd4e-403e-81bc-26507fc866f8', '07a409f7-ee38-43b1-938c-f44a4766e2a7')
    ORDER BY created_at
""")

rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row[0]}")
    print(f"  标题: {row[1]}")
    print(f"  消息数: {row[2]}")
    print(f"  创建时间: {row[3]}")
    print()

conn.close()