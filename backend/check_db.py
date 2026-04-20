#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3

db_path = 'C:/Users/40968/.omniagent/chat_history.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看session信息
cursor.execute("SELECT id, title, message_count FROM chat_sessions WHERE id='7630c558-3f22-4ed5-b7c4-3af55ce6d8dc'")
session = cursor.fetchone()
print(f'session message_count: {session[2]}')

# 实际消息数
cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id='7630c558-3f22-4ed5-b7c4-3af55ce6d8dc'")
actual = cursor.fetchone()[0]
print(f'实际消息数: {actual}')

conn.close()