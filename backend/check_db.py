import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
c = conn.cursor()

# 查看chat_messages表结构
c.execute("PRAGMA table_info(chat_messages)")
print("=== chat_messages表结构 ===")
for row in c.fetchall():
    print(row)

# 查看最近的消息
print("\n=== 最近10条assistant消息 ===")
c.execute("SELECT id, session_id, role, length(execution_steps), length(content) FROM chat_messages WHERE role='assistant' ORDER BY id DESC LIMIT 10")
for row in c.fetchall():
    print(f"id={row[0]}, steps_len={row[3]}, content_len={row[4]}")

# 查看字段内容长度分布
print("\n=== execution_steps 长度分布 ===")
c.execute("SELECT MIN(length(execution_steps)), MAX(length(execution_steps)), AVG(length(execution_steps)) FROM chat_messages WHERE execution_steps IS NOT NULL")
row = c.fetchone()
print(f"MIN={row[0]}, MAX={row[1]}, AVG={row[2]}")

conn.close()
