import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".omniagent" / "chat_history.db"
print('DB Path:', DB_PATH)

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

# 获取最后一条 assistant 消息
cursor.execute('''
SELECT id, session_id, content 
FROM chat_messages 
WHERE role = 'assistant' 
ORDER BY id DESC 
LIMIT 1
''')
row = cursor.fetchone()

if row:
    print(f'\n要删除的消息: ID={row[0]}, session_id={row[1]}')
    print(f'Content preview: {row[2][:100] if row[2] else None}...')
    
    # 删除这条消息
    cursor.execute('DELETE FROM chat_messages WHERE id = ?', (row[0],))
    print(f'\n已删除消息 ID={row[0]}')
    
    conn.commit()
else:
    print('没有找到 assistant 消息')

conn.close()
