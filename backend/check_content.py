import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
c = conn.cursor()

# 查看消息667和702的content
for msg_id in [667, 702]:
    c.execute("SELECT id, role, content, length(execution_steps) FROM chat_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    if row:
        print(f"=== 消息 {msg_id} ===")
        print(f"role: {row[1]}")
        print(f"content: {row[2]}")
        print(f"steps长度: {row[3]}")
        print()

conn.close()
