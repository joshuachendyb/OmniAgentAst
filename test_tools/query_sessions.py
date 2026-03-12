import sqlite3

# 连接数据库
conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

# 先查看表结构
cursor.execute("PRAGMA table_info(chat_sessions)")
columns = cursor.fetchall()
print("chat_sessions 表结构:")
print("-" * 80)
for col in columns:
    print(f"{col[1]:<20} {col[2]:<15}")

print("\n" + "=" * 80 + "\n")

# 查询最近10个会话（去掉不存在的字段）
cursor.execute('''
    SELECT id, title, message_count, title_locked, version, updated_at
    FROM chat_sessions
    ORDER BY id DESC
    LIMIT 10
''')

rows = cursor.fetchall()

# 打印结果
print(f"{'ID':<5} {'标题':<40} {'消息数':<8} {'锁定':<6} {'版本':<6} {'更新时间'}")
print('-' * 100)
for row in rows:
    print(f"{row[0]:<5} {row[1][:38]:<40} {row[2]:<8} {row[3]:<6} {row[4]:<6} {row[5]}")

conn.close()