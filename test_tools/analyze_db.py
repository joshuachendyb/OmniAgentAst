import sqlite3

# 连接数据库
conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

print("=" * 80)
print("数据库分析报告")
print("=" * 80)

# 1. 统计总数
cursor.execute('SELECT COUNT(*) FROM chat_sessions')
session_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM chat_messages')
message_count = cursor.fetchone()[0]

print(f"\n1. 基本统计")
print(f"   会话总数: {session_count}")
print(f"   消息总数: {message_count}")

# 2. 按消息数分组统计
print(f"\n2. 按消息数分组统计")
print(f"   消息数\t会话数")
print(f"   {'-'*20}\t{'-'*10}")

cursor.execute('''
    SELECT message_count, COUNT(*) as count
    FROM chat_sessions
    GROUP BY message_count
    ORDER BY message_count
''')

rows = cursor.fetchall()
for row in rows:
    print(f"   {row[0]}\t{row[1]}")

# 3. 标题锁定状态统计
print(f"\n3. 标题锁定状态统计")
print(f"   状态\t\t会话数")
print(f"   {'-'*20}\t{'-'*10}")

cursor.execute('''
    SELECT 
        CASE WHEN title_locked = 1 THEN '已锁定'
        WHEN title_locked = 0 THEN '未锁定'
        ELSE '未知'
    END as status,
        COUNT(*) as count
    FROM chat_sessions
    GROUP BY title_locked
''')

rows = cursor.fetchall()
for row in rows:
    print(f"   {row[0]}\t{row[1]}")

# 4. 版本号统计
print(f"\n4. 版本号统计")
print(f"   版本号\t会话数")
print(f"   {'-'*20}\t{'-'*10}")

cursor.execute('''
    SELECT version, COUNT(*) as count
    FROM chat_sessions
    GROUP BY version
    ORDER BY version
''')

rows = cursor.fetchall()
for row in rows:
    print(f"   {row[0]}\t{row[1]}")

# 5. 删除状态统计
print(f"\n5. 删除状态统计")
print(f"   状态\t\t会话数")
print(f"   {'-'*20}\t{'-'*10}")

cursor.execute('''
    SELECT 
        CASE WHEN is_deleted = 1 THEN '已删除'
        WHEN is_deleted = 0 THEN '未删除'
        ELSE '未知'
    END as status,
        COUNT(*) as count
    FROM chat_sessions
    GROUP BY is_deleted
''')

rows = cursor.fetchall()
for row in rows:
    print(f"   {row[0]}\t{row[1]}")

# 6. 最近更新的会话
print(f"\n6. 最近更新的5个会话")
print(f"   ID\t\t\t标题\t\t\t消息数\t更新时间")
print(f"   {'-'*40}\t{'-'*30}\t{'-'*8}\t{'-'*20}")

cursor.execute('''
    SELECT id, title, message_count, updated_at
    FROM chat_sessions
    WHERE is_deleted = 0
    ORDER BY updated_at DESC
    LIMIT 5
''')

rows = cursor.fetchall()
for row in rows:
    print(f"   {row[0][:20]}\t{row[1][:20]:20}\t{row[2]}\t{row[3]}")

# 7. 有消息的会话数量
cursor.execute('SELECT COUNT(*) FROM chat_sessions WHERE message_count > 0')
sessions_with_messages = cursor.fetchone()[0]

print(f"\n7. 关键指标")
print(f"   有消息的会话数: {sessions_with_messages}")
print(f"   无消息的会话数: {session_count - sessions_with_messages}")
print(f"   平均每会话消息数: {message_count / sessions_with_messages if sessions_with_messages > 0 else 0:.2f}")

conn.close()

print("\n" + "=" * 80)
print("分析完成")
print("=" * 80)