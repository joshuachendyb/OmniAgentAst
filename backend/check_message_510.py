import sqlite3
from pathlib import Path

db_path = Path.home() / ".omniagent" / "chat_history.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

msg_id = 510

# 查询消息内容和 execution_steps
cur.execute("""
    SELECT id, role, content, LENGTH(execution_steps) as steps_size
    FROM chat_messages 
    WHERE id = ?
""", (msg_id,))

result = cur.fetchone()
print(f"msg_id: {result[0]}")
print(f"role: {result[1]}")
print(f"content (first 500 chars): {result[2][:500] if result[2] else 'None'}")
print(f"execution_steps size: {result[3] / 1024 / 1024:.2f} MB")

# 解析 execution_steps
cur.execute("SELECT execution_steps FROM chat_messages WHERE id = ?", (msg_id,))
steps_data = cur.fetchone()[0]
if steps_data:
    import json
    steps = json.loads(steps_data)
    print(f"\n步骤数量: {len(steps)}")
    
    # 检查每个步骤的 execution_result 大小
    for i, step in enumerate(steps[:5]):  # 只看前5个
        step_size = len(json.dumps(step))
        print(f"  步骤{i}: type={step.get('type')}, tool_name={step.get('tool_name')}, size={step_size/1024:.2f} KB")
        
        # 检查 execution_result
        exec_result = step.get('execution_result')
        if exec_result:
            result_size = len(json.dumps(exec_result))
            print(f"    execution_result 大小: {result_size / 1024:.2f} KB")
            # 打印 execution_result 的部分内容
            if isinstance(exec_result, dict):
                print(f"    execution_result keys: {list(exec_result.keys())[:10]}")

conn.close()
