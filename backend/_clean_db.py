import sqlite3, os
db = os.path.expanduser("~/.omniagent/chat_history.db")
conn = sqlite3.connect(db)
cur = conn.cursor()
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row)
conn.close()
