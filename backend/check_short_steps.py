import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 查看steps数量明显偏少的assistant消息（少于5条）
print("=== steps数量少于5条的assistant消息 ===")
c.execute("""
    SELECT id, session_id, execution_steps
    FROM chat_messages 
    WHERE role='assistant' 
    AND execution_steps IS NOT NULL 
    AND execution_steps != ''
    AND json_valid(execution_steps) = 1
    AND json_array_length(execution_steps) < 5
    ORDER BY id DESC
    LIMIT 20
""")
for row in c.fetchall():
    steps = json.loads(row[2]) if isinstance(row[2], str) else row[2]
    print(f"id={row[0]}, steps_count={len(steps)}")
    # 打印step类型
    types = [s.get('type') for s in steps]
    print(f"  types: {types}")

conn.close()
