# -*- coding: utf-8 -*-
import sqlite3

# 使用正确的数据库路径
db_path = "C:/Users/40968/.omniagent/chat_history.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看chat_messages表结构
cursor.execute("PRAGMA table_info(chat_messages)")
print('chat_messages表字段:')
for col in cursor.fetchall():
    print(f'  {col[1]} ({col[2]})')

# 查询message 1138
print('\n=== 查询Message 1138 ===')
cursor.execute("SELECT * FROM chat_messages WHERE id = 1138")
msg = cursor.fetchone()
if msg:
    # 获取列名
    cursor.execute("PRAGMA table_info(chat_messages)")
    columns = [col[1] for col in cursor.fetchall()]
    
    for i, val in enumerate(msg):
        col_name = columns[i]
        print(f'  {col_name}: {val}')
        
    # 分析content中的steps
    content_idx = columns.index('content')
    if msg[content_idx]:
        import json
        try:
            data = json.loads(msg[content_idx])
            print(f'\n  JSON字段: {list(data.keys())}')
            
            if 'executionSteps' in data:
                steps = data['executionSteps']
                print(f'  executionSteps数量: {len(steps)}')
                print(f'  step类型列表:')
                for i, s in enumerate(steps):
                    step_type = s.get('type', 'unknown')
                    tool_name = s.get('tool_name', s.get('action', 'unknown'))
                    print(f'    step_{i}: type={step_type}, tool={tool_name}')
            else:
                print('  无executionSteps字段')
                
        except Exception as e:
            print(f'  解析JSON失败: {e}')
else:
    print('  未找到message 1138')

conn.close()