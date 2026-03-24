import sqlite3
import json

db_path = r"C:\Users\40968\.omniagent\chat_history.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 查找最新的assistant消息
c.execute("""
    SELECT id, content, execution_steps 
    FROM chat_messages 
    WHERE role='assistant' AND execution_steps IS NOT NULL
    ORDER BY id DESC
    LIMIT 1
""")

r = c.fetchone()
if r:
    print(f"Message ID: {r[0]}")
    print(f"Content length: {len(r[1]) if r[1] else 0}")
    
    if r[2]:
        steps = json.loads(r[2])
        print(f"Steps count: {len(steps)}")
        
        # 打印前5个step的type
        for i, s in enumerate(steps[:5]):
            print(f"  {i+1}. type={s.get('type')}")

conn.close()
