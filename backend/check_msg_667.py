import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 查看id=667的详细内容
c.execute("SELECT id, role, content, execution_steps, timestamp FROM chat_messages WHERE id = 667")
row = c.fetchone()
if row:
    print(f"id={row[0]}, role={row[1]}")
    print(f"timestamp={row[4]}")
    print(f"content={row[2][:100]}...")
    if row[3]:
        steps = json.loads(row[3])
        print(f"steps_count={len(steps)}")
        for i, s in enumerate(steps):
            print(f"  {i}: {s.get('type')}")

# 再看看668, 669
for msg_id in [668, 669]:
    c.execute("SELECT id, role, content, execution_steps, timestamp FROM chat_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    if row:
        print(f"\n=== id={row[0]} ===")
        print(f"timestamp={row[4]}")
        if row[3]:
            steps = json.loads(row[3])
            print(f"steps_count={len(steps)}")
            for i, s in enumerate(steps):
                print(f"  {i}: {s.get('type')}")

conn.close()
