import sqlite3
import json
from pathlib import Path

db_path = Path.home() / ".omniagent" / "chat_history.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

msg_id = 510

cur.execute("SELECT execution_steps FROM chat_messages WHERE id = ?", (msg_id,))
steps_data = cur.fetchone()[0]
steps = json.loads(steps_data)

# 找到 action_tool 步骤
for step in steps:
    if step.get('type') == 'action_tool' and step.get('tool_name') == 'list_directory':
        exec_result = step.get('execution_result', {})
        
        # 分析 execution_result 结构
        print("=== execution_result 分析 ===")
        print(f"success: {exec_result.get('success')}")
        print(f"total: {exec_result.get('total')}")
        print(f"directory: {exec_result.get('directory')}")
        
        entries = exec_result.get('entries', [])
        print(f"entries 数量: {len(entries)}")
        
        # 计算 entries 的总大小
        entries_size = len(json.dumps(entries))
        print(f"entries JSON 大小: {entries_size / 1024 / 1024:.2f} MB")
        
        # 显示前5个条目
        print("\n前5个条目:")
        for i, entry in enumerate(entries[:5]):
            print(f"  {i+1}. {entry}")
        
        break

conn.close()
