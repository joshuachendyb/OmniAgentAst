# -*- coding: utf-8 -*-
import sqlite3

conn = sqlite3.connect(r'D:\OmniAgentAs-desk\backend\chat_app.db')
cursor = conn.cursor()

# 查看表结构
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("=== Tables in chat_app.db ===")
for t in tables:
    print(t[0])
    # 查看每个表的结构
    cursor.execute(f"PRAGMA table_info({t[0]})")
    columns = cursor.fetchall()
    for c in columns:
        print(f"  - {c[1]} ({c[2]})")
    print()

conn.close()