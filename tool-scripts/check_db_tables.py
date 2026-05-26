#!/usr/bin/env python3
"""
检查数据库中的表
"""
import sqlite3

def check_tables():
    db_path = "C:/Users/40968/.omniagent/chat_history.db"
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("数据库中的表:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_tables()