import sqlite3

# 连接到数据库
conn = sqlite3.connect('chat_app.db')
cursor = conn.cursor()

# 检查所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Database tables:", [table[0] for table in tables])

if 'chat_sessions' in [table[0] for table in tables]:
    # 检查表结构
    print("\nchat_sessions table structure:")
    cursor.execute('PRAGMA table_info(chat_sessions)')
    columns = cursor.fetchall()
    for col in columns:
        print(f'  {col[1]} ({col[2]}) - PK:{col[5]}, NOT NULL:{col[3]}, DEFAULT:{col[4]}')
    
    # 检查 is_valid 字段值分布
    print("\nChecking is_valid field distribution:")
    try:
        cursor.execute('SELECT is_valid, COUNT(*) AS count FROM chat_sessions GROUP BY is_valid')
        results = cursor.fetchall()
        print('is_valid field value distribution:')
        for row in results:
            print(f'  is_valid={row[0]}, count={row[1]}')
    except sqlite3.OperationalError as e:
        print(f'Query error on is_valid field: {e}')
else:
    print("\nchat_sessions table does not exist")

conn.close()