import sqlite3
import json

db_path = 'C:/Users/40968/.omniagent/chat_history.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查询 message_id = 1041 的消息
cursor.execute('SELECT * FROM messages WHERE id = 1041')
row = cursor.fetchone()

if row:
    print("=" * 60)
    print(f"Message ID: {row['id']}")
    print(f"Session ID: {row['session_id']}")
    print(f"Role: {row['role']}")
    print(f"Timestamp: {row['timestamp']}")
    print()
    
    # 解析 execution_steps
    if row['execution_steps']:
        try:
            steps = json.loads(row['execution_steps'])
            print(f"Total steps: {len(steps)}")
            print()
            
            # 查找所有 observation 步骤
            for step in steps:
                if step.get('type') == 'observation':
                    print("=" * 60)
                    print(f"Observation step: {step.get('step')}")
                    print(f"Fields: {list(step.keys())}")
                    print()
                    print("Full data:")
                    print(json.dumps(step, indent=2, ensure_ascii=False))
                    break
        except:
            print("Failed to parse execution_steps")
else:
    print("Message 1041 not found")

conn.close()
