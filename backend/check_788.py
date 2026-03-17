import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
c = conn.cursor()

# Get all messages in session 6658e10c-a459-4194-a7fe-12f501fffcae
c.execute("""
    SELECT id, role, content, execution_steps 
    FROM chat_messages 
    WHERE session_id = '6658e10c-a459-4194-a7fe-12f501fffcae'
    ORDER BY id
""")

rows = c.fetchall()

print(f"=== Session 6658e10c - {len(rows)} messages ===\n")

for row in rows:
    msg_id, role, content, steps_json = row
    
    print(f"Message {msg_id} ({role}):")
    
    if steps_json:
        try:
            steps = json.loads(steps_json)
            print(f"  Steps: {len(steps)} - {[s.get('type') for s in steps]}")
            # Show content preview
            print(f"  Content: {str(content)[:50] if content else 'None'}...")
        except:
            print(f"  Steps: (parse error)")
    else:
        print(f"  Steps: None")
    print()

conn.close()
