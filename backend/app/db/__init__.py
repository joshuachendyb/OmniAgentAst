"""DB SDK

管理3个SQLite数据库：
- chat_history.db: 对话会话和消息
- operations.db: 文件操作和任务记录
- tool_observer.db: 工具调用审计（后续实现）

使用方式:
    from app.db import db
    
    with db.get_conn("chat") as conn:
        conn.execute("SELECT ...")

禁止行为:
    - 禁止手动conn.commit()
    - 禁止手动conn.close()
    - 禁止使用裸连接

Author: 小沈 - 2026-05-28
"""

from app.db.database import db

__all__ = ["db"]
