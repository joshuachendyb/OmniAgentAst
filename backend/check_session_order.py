import sqlite3
import json
from pathlib import Path

db_path = Path.home() / ".omniagent" / "chat_history.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

session_id = 'cf91de03-c15a-4e27-9d81-096f2dbe9585'

# 查询所有消息，按ID排序
cur.execute("""
    SELECT id, role, LENGTH(execution_steps) as steps_size
    FROM chat_messages 
    WHERE session_id = ?
    ORDER BY id ASC
""", (session_id,))

rows = cur.fetchall()
print(f"=== 会话消息列表 (共 {len(rows)} 条) ===\n")

# 显示最后10条消息
print("最后10条消息:")
for i, row in enumerate(rows[-10:]):
    actual_idx = len(rows) - 10 + i
    msg_id = row[0]
    role = row[1]
    steps_size = row[2] / 1024 / 1024 if row[2] else 0
    marker = " <-- msg_id=510" if msg_id == 510 else ""
    print(f"  [{actual_idx}] id={msg_id}, role={role}, steps_size={steps_size:.2f} MB{marker}")

# 检查 msg_id=510 的内容
print("\n=== msg_id=510 内容 ===")
cur.execute("SELECT content, LENGTH(execution_steps) FROM chat_messages WHERE id = 510")
result = cur.fetchone()
print(f"content: {result[0][:200] if result[0] else 'None'}...")
print(f"execution_steps 大小: {result[1]/1024/1024:.2f} MB")

# 解析 execution_steps，检查每条消息的 type
cur.execute("SELECT execution_steps FROM chat_messages WHERE id = 510")
steps = json.loads(cur.fetchone()[0])
print(f"\n步骤列表 (共 {len(steps)} 个):")
for i, step in enumerate(steps):
    print(f"  [{i}] type={step.get('type')}, tool_name={step.get('tool_name')}, has_result={bool(step.get('execution_result'))}")

conn.close()
