import sqlite3
conn = sqlite3.connect('backend/chat_app.db')
cur = conn.cursor()
# 列出所有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:")
for r in cur.fetchall():
    print(r)
conn.close()