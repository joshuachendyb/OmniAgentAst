import sqlite3
import json
from pathlib import Path

DB_PATH = Path.home() / ".omniagent" / "chat_history.db"
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()
cursor.execute("""
    SELECT session_id, role, content, execution_steps 
    FROM chat_messages 
    WHERE session_id = '4852d1df-f31d-4108-9e51-d7887d8847ae' 
    ORDER BY id
""")
rows = cursor.fetchall()
print(f'Found {len(rows)} messages for session 4852d1df-f31d-4108-9e51-d7887d8847ae')
for row in rows:
    role = row[1]
    content_len = len(row[2]) if row[2] else 0
    print(f'Role: {role}, Content length: {content_len}')
    if row[3]:
        steps = json.loads(row[3])
        print(f'  Steps count: {len(steps)}')
        for i, step in enumerate(steps):
            print(f'    Step {i+1}: type={step.get("type")}, step={step.get("step")}')
    else:
        print('  Steps: None')
    print('---')
conn.close()
