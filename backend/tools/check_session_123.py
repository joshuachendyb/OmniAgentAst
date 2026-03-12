import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

# 查找123会话
cursor.execute("SELECT id, title, message_count FROM chat_sessions WHERE title LIKE '123%' ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()

if row:
    session_id, title, message_count = row
    print(f"会话ID: {session_id}")
    print(f"标题: {title}")
    print(f"message_count字段值: {message_count}")
    
    # 查询实际消息数
    cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
    actual_count = cursor.fetchone()[0]
    print(f"实际消息数: {actual_count}")
    
    # 查询最近的几条消息
    cursor.execute("SELECT id, role, SUBSTR(content, 1, 50) as content FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 5", (session_id,))
    messages = cursor.fetchall()
    print(f"\n最近{len(messages)}条消息:")
    for msg in messages:
        print(f"  {msg[0]} | {msg[1]} | {msg[2]}...")
else:
    print("未找到标题包含'123'的会话")

conn.close()