import sqlite3

# 连接数据库
conn = sqlite3.connect('C:/Users/40968/.omniagent/chat_history.db')
cursor = conn.cursor()

print("=" * 80)
print("数据库状态检查")
print("=" * 80)

# 1. 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("\n数据库中的表:")
for table in tables:
    print(f"  - {table[0]}")

if len(tables) == 0:
    print("\n⚠️ 数据库为空，没有表")
    conn.close()
    exit(0)

# 2. 查询表结构
for table in tables:
    table_name = table[0]
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    print(f"\n{table_name} 表结构:")
    print(f"{'字段名':<20} {'类型':<20} {'允许NULL':<10}")
    print("-" * 60)
    for col in columns:
        print(f"{col[1]:<20} {col[2]:<20} {'YES' if col[3] == 0 else 'NO':<10}")

# 3. 查询会话数量
cursor.execute("SELECT COUNT(*) FROM chat_sessions")
session_count = cursor.fetchone()[0]
print(f"\n会话总数: {session_count}")

# 4. 查询消息数量
cursor.execute("SELECT COUNT(*) FROM chat_messages")
message_count = cursor.fetchone()[0]
print(f"消息总数: {message_count}")

conn.close()

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)