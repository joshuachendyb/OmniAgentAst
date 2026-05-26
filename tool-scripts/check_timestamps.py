#!/usr/bin/env python3
"""
检查数据库中的时间戳格式
"""
import sqlite3
import json
import sys
from datetime import datetime

def check_timestamps():
    db_path = "C:/Users/40968/.omniagent/chat_history.db"
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查找最新的消息
        cursor.execute('''
            SELECT id, conversation_id, role, timestamp, execution_steps 
            FROM messages 
            WHERE execution_steps IS NOT NULL 
            ORDER BY id DESC 
            LIMIT 5
        ''')
        
        messages = cursor.fetchall()
        
        for msg in messages:
            msg_id, conv_id, role, msg_timestamp, exec_steps_json = msg
            print(f"\n=== 消息ID: {msg_id} ===")
            print(f"角色: {role}")
            print(f"消息timestamp: {msg_timestamp}")
            
            if exec_steps_json:
                try:
                    steps = json.loads(exec_steps_json)
                    print(f"执行步骤数量: {len(steps)}")
                    
                    # 显示前5个步骤
                    for i, step in enumerate(steps[:5]):
                        step_type = step.get('type', 'unknown')
                        step_timestamp = step.get('timestamp', 'N/A')
                        step_name = step.get('name', 'N/A')
                        step_data = step.get('data', {})
                        
                        print(f"\n  步骤{i+1}:")
                        print(f"    type: {step_type}")
                        print(f"    name: {step_name}")
                        print(f"    timestamp: {step_timestamp}")
                        print(f"    timestamp类型: {type(step_timestamp)}")
                        
                        # 如果是数字，转换为可读时间
                        if isinstance(step_timestamp, (int, float)):
                            if step_timestamp > 1000000000000:  # 13位毫秒
                                readable = datetime.fromtimestamp(step_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                                print(f"    可读时间: {readable}")
                            elif step_timestamp > 1000000:  # 6位秒
                                readable = datetime.fromtimestamp(step_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                                print(f"    可读时间: {readable}")
                            else:
                                print(f"    ⚠️ 时间戳太小，可能是无效数据")
                                
                except json.JSONDecodeError as e:
                    print(f"  解析JSON失败: {e}")
                    
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_timestamps()