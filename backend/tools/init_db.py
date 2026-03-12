"""
初始化数据库表的工具脚本
"""

import sys
import os

# 添加项目路径到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))

from app.api.v1.sessions import _init_database

def initialize_database():
    print("开始初始化数据库...")
    try:
        _init_database()
        print("数据库初始化完成！")
        
        # 验证表是否创建成功
        import sqlite3
        conn = sqlite3.connect('chat_app.db')
        cursor = conn.cursor()
        
        # 检查所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"数据库中已创建的表: {[table[0] for table in tables]}")
        
        if 'chat_sessions' in [table[0] for table in tables]:
            print("✓ chat_sessions 表创建成功")
            
            # 检查表结构
            cursor.execute('PRAGMA table_info(chat_sessions)')
            columns = cursor.fetchall()
            print("\nchat_sessions 表结构:")
            for col in columns:
                print(f'  {col[1]} ({col[2]}) - DEFAULT: {col[4]}')
                
            # 检查 is_valid 字段是否存在
            column_names = [col[1] for col in columns]
            if 'is_valid' in column_names:
                print("\n✓ is_valid 字段已正确添加到表中")
            else:
                print("\n✗ is_valid 字段未找到")
        
        conn.close()
        
    except Exception as e:
        print(f"初始化数据库时发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    initialize_database()