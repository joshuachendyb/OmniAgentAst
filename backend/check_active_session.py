import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

print("=== 检查最近活跃的会话 ===")

# 检查最近保存消息的会话
session_id = '07a409f7-ee38-43b1-938c-f44a4766e2a7'

cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
session = cursor.fetchone()

if session:
    print(f"\n会话ID: {session[0]}")
    print(f"标题: {session[1]}")
    print(f"message_count: {session[4]}")
    
    # 查询这个会话的所有消息
    cursor.execute("SELECT id, role, SUBSTR(content, 1, 100), timestamp FROM chat_messages WHERE session_id = ? ORDER BY id", (session_id,))
    messages = cursor.fetchall()
    
    print(f"\n实际消息数: {len(messages)}")
    print("\n消息列表:")
    for i, msg in enumerate(messages, 1):
        print(f"{i}. [{msg[1]}] {msg[2]}... ({msg[3][:19]})")
else:
    print(f"会话 {session_id} 不存在")

# 检查123会话
session_id_123 = 'd5c36d79-cd4e-403e-81bc-26507fc866f8'
print("\n=== 检查123会话 ===")

cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id_123,))
session_123 = cursor.fetchone()

if session_123:
    print(f"\n会话ID: {session_123[0]}")
    print(f"标题: {session_123[1]}")
    print(f"message_count: {session_123[4]}")
    
    cursor.execute("SELECT id, role, SUBSTR(content, 1, 100), timestamp FROM chat_messages WHERE session_id = ? ORDER BY id", (session_id_123,))
    messages_123 = cursor.fetchall()
    
    print(f"\n实际消息数: {len(messages_123)}")
    if messages_123:
        print("\n消息列表:")
        for i, msg in enumerate(messages_123, 1):
            print(f"{i}. [{msg[1]}] {msg[2]}... ({msg[3][:19]})")
    else:
        print("没有任何消息")
else:
    print(f"会话 {session_id_123} 不存在")

conn.close()