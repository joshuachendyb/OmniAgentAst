import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 查看消息723 - 没有execution_steps
c.execute("SELECT id, role, content, execution_steps FROM chat_messages WHERE id = 723")
row = c.fetchone()
if row:
    print(f"消息723: role={row['role']}, content={row['content']}")
    print(f"  execution_steps: {row['execution_steps']}")

# 查看消息725 - 有execution_steps
c.execute("SELECT id, role, content, execution_steps FROM chat_messages WHERE id = 725")
row = c.fetchone()
if row:
    print(f"\n消息725: role={row['role']}, content={row['content']}")
    if row['execution_steps']:
        steps = json.loads(row['execution_steps'])
        print(f"  execution_steps数量: {len(steps)}")
        print(f"  第一个step类型: {steps[0].get('type') if steps else 'N/A'}")

# 查看会话中哪些assistant消息没有execution_steps
print("\n=== 没有execution_steps的assistant消息 ===")
c.execute("""
    SELECT id, role, content, timestamp
    FROM chat_messages 
    WHERE role='assistant' AND (execution_steps IS NULL OR execution_steps = '')
    ORDER BY id DESC
""")
for row in c.fetchall():
    print(f"id={row[0]}, timestamp={row[3]}, content={row['content'][:50]}...")

conn.close()
