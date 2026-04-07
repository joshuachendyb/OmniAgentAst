import sqlite3
import json

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cur = conn.cursor()

# Get table schema
print("=== Table: chat_messages ===")
cur.execute("PRAGMA table_info(chat_messages)")
for row in cur.fetchall():
    print(row)

print("\n=== Table: chat_sessions ===")
cur.execute("PRAGMA table_info(chat_sessions)")
for row in cur.fetchall():
    print(row)