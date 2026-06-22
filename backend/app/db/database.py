# -*- coding: utf-8 -*-
"""DB SDK - 统一数据库操作接口

管理3个SQLite数据库:
- chat_history.db: 对话会话和消息
- operations.db: 文件操作和任务记录
- tool_observer.db: 工具调用审计(后续实现)

使用方式:
    from app.db import db
    
    with db.get_conn("chat") as conn:
        conn.execute("SELECT ...")

设计原则:
- 统一入口:所有DB操作通过db.get_conn()
- 自动事务:上下文管理器自动commit/rollback/close
- 摒弃裸连接:禁止手动管理连接
- SRP拆分:初始化逻辑委托给db_initializer

Author: 小沈 - 2026-05-28
小欧 2026-06-18 SRP拆分: 初始化→db_initializer
小健 2026-06-18 删除向后兼容迁移代码(db_migrator.py)
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator
from app.utils.logger import logger
from app.db.db_initializer import (
    init_chat_db, init_operations_db, init_task_tracker_db,
)



class DatabaseManager:
    """统一数据库管理器(SDK核心) — 仅负责连接管理"""
    
    def __init__(self):
        """初始化数据库管理器"""
        self._db_dir = Path.home() / ".omniagent"
        self._db_paths = {
            "chat": self._db_dir / "chat_history.db",
            "operations": self._db_dir / "operations.db",
            "observer": self._db_dir / "tool_observer.db",
            "task_tracker": self._db_dir / "task_tracker.db",
        }
        self._db_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_conn(self, db_name: str = "chat") -> Iterator[sqlite3.Connection]:
        """获取数据库连接(上下文管理器)
        
        使用方式:
            with db.get_conn("chat") as conn:
                conn.execute("SELECT ...")
        
        自动处理:
            - 正常退出: commit + close
            - 异常退出: rollback + close
            - 无论如何: 都会关闭连接
        
        支持的db_name: chat, operations, observer, task_tracker
        """
        conn = None
        try:
            if db_name not in self._db_paths:
                raise ValueError(
                    f"Unknown database: {db_name}. "
                    f"Supported: {list(self._db_paths.keys())}"
                )
            
            db_path = self._db_paths[db_name]
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            
            yield conn
            
            conn.commit()
            
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            
            logger.error(f"DB operation failed [{db_name}]: {e}")
            raise
            
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
    def init(self):
        """初始化所有数据库(应用启动时调用)"""
        logger.info("Initializing all databases...")
        
        init_chat_db(self.get_conn)
        init_operations_db(self.get_conn)
        init_task_tracker_db(self.get_conn)

        
        logger.info("All databases initialized successfully")
    
    def init_observer(self):
        """初始化observer数据库(后续实现ToolObserver时调用)"""
        logger.info("Observer database initialized (placeholder)")


# 全局SDK实例(唯一入口)
db = DatabaseManager()
