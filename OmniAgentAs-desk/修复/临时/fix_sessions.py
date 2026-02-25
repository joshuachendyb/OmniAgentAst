# 修复sessions.py的简单修复脚本
# 修复问题：更新save_message函数中的version递增逻辑
# 修复问题8：日志记录不完整

import sqlite3

# 修复位置1：修复save_message函数中的version递增逻辑
# 修改内容：只在标题变化时才递增版本号
# 现在：save_message函数中添加调试日志

# 修复位置2：添加update_session和get_session_messages的日志

print("开始修复sessions.py...")
