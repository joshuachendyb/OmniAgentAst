import sqlite3
import json

conn = sqlite3.connect('backend/data/chat_app.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cursor.fetchall()])

# 查询 session 表
session_id = "ff80fe35-6f3c-49cd-9975-352a655b3b05"
message_id = "220"

cursor.execute("SELECT raw_data FROM sessions WHERE session_id=?", (session_id,))
row = cursor.fetchone()

if row:
    raw = json.loads(row[0])
    messages = raw.get('messages', [])
    print(f"\nmessages 总数: {len(messages)}")
    
    # 找 messageId = 220
    for msg in messages:
        if msg.get('messageId') == '220':
            print(f"\n找到 messageId=220")
            steps = msg.get('executionSteps', [])
            print(f"executionSteps 总数: {len(steps)}")
            
            for i, step in enumerate(steps):
                print(f"\n第{i+1}步: type={step.get('type')}, step={step.get('step')}")
                if 'raw_data' in step:
                    rd = step['raw_data']
                    if isinstance(rd, dict):
                        print(f"  raw_data keys: {list(rd.keys())}")
                        if 'matches' in rd:
                            print(f"  matches 数量: {len(rd['matches'])}")
                        if 'total' in rd:
                            print(f"  total: {rd['total']}")
                        if 'total_matches' in rd:
                            print(f"  total_matches: {rd['total_matches']}")
            break
else:
    print("未找到 session")

conn.close()

if row:
    raw = json.loads(row[0])
    steps = raw.get('executionSteps', [])
    print(f"executionSteps 总数: {len(steps)}")
    print()
    
    for i, step in enumerate(steps):
        print(f"第{i+1}步: type={step.get('type')}, step={step.get('step')}")
        if 'raw_data' in step:
            rd = step['raw_data']
            if isinstance(rd, dict):
                print(f"  raw_data keys: {list(rd.keys())}")
                if 'matches' in rd:
                    print(f"  matches 数量: {len(rd['matches'])}")
                if 'total' in rd:
                    print(f"  total: {rd['total']}")
                if 'total_matches' in rd:
                    print(f"  total_matches: {rd['total_matches']}")
        print()
else:
    print("未找到")

conn.close()