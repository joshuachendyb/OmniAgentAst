import sqlite3

conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

print("=== 最近保存的消息 ===")

cursor.execute("""
    SELECT m.session_id, s.title, m.role, SUBSTR(m.content, 1, 50), m.timestamp
    FROM chat_messages m
    JOIN chat_sessions s ON m.session_id = s.id
    ORDER BY m.timestamp DESC
    LIMIT 20
""")

rows = cursor.fetchall()
print(f"{'会话ID':12} | {'标题':20} | {'角色':12} | {'内容预览':30} | {'时间戳':25}")
print("-" * 110)

for row in rows:
    session_id = str(row[0])[:8] + '...' if row[0] else 'None'
    title = str(row[1])[:20] if row[1] else 'None'
    role = row[2]
    content = str(row[3])[:30] + '...' if row[3] else 'None'
    timestamp = str(row[4])[:25] if row[4] else 'None'
    
    print(f"{session_id:<12} | {title:<20} | {role:<12} | {content:<30} | {timestamp}")

conn.close()