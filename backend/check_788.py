import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
c = conn.cursor()

# Check message 794
c.execute("SELECT id, role, content, execution_steps FROM chat_messages WHERE id = 794")
row = c.fetchone()

if row:
    print(f"=== Message {row[0]} ===")
    print(f"Role: {row[1]}")
    print(f"Content: {row[2]}")
    
    if row[3]:
        try:
            steps = json.loads(row[3])
            print(f"\nExecution steps count: {len(steps)}")
            print("Step types:")
            for s in steps:
                print(f"  - {s.get('type')}")
        except Exception as e:
            print(f"Parse error: {e}")
    else:
        print("No execution_steps")
else:
    print("Message 794 not found")

conn.close()
