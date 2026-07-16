# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - chat库采用DELETE journal模式,其他库维持WAL; Windows大库场景设计选择
# 2026-07-15 - 小欧 - get_conn异常分支拆分: 原except Exception兜底所有异常并记"DB operation failed", 业务异常(如rename目标已存在抛FileExistsError)被误报为数据库故障, 且被execute_with_safety二次记日志形成双重日志(首条为误报)。改后仅sqlite3.Error记DB错误日志, 业务异常仅rollback后raise不误报。
# 2026-07-17 - 小欧 - chat库改回WAL,三库统一WAL。背景因果(经验累积,勿删): 07-14的DELETE源于误诊——
#            当时遇Errno22误判为"WAL-shm在Windows 2GB+库并发读写不稳"; 同日《后端step单步保存设计说明书》v1.2已更正
#            Errno22真实根因为time_utils.ensure_timestamp_milliseconds潜伏bug(Python3.13宽松fromisoformat+漏捕OSError),与WAL无关,
#            DELETE改动属误诊白做但无害、当时未回退。2026-07-17 E2E验证暴露DELETE模式在chat_message_steps膨胀185万行/2.7GB时
#            写I/O拥塞(每次写journal+fsync)致create_session同步写>10s超时,故回归WAL统一三库消除写拥塞。详见notes/经验累积文档。
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
from app.logger import logger
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
            
            # 全部库统一WAL模式(含chat) — 小欧 2026-07-17
            # 历史因果(经验累积,勿删): 2026-07-14曾将chat改为DELETE,系误诊"WAL-shm在Windows 2GB+库并发读写Errno22"所致;
            #   同日《后端step单步保存设计说明书》v1.2已更正Errno22真实根因为time_utils潜伏bug(与WAL无关),DELETE属误诊白做但无害、当时未回退。
            #   2026-07-17 E2E验证暴露DELETE模式在chat_message_steps膨胀185万行/2.7GB时写I/O拥塞(每次写journal+fsync),
            #   致create_session同步写>10s超时;故改回WAL统一三库,消除写拥塞。
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            # M-05: SQLite默认OFF，外键约束不生效 — 小欧 2026-07-10
            conn.execute("PRAGMA foreign_keys=ON")
            
            yield conn
            
            conn.commit()
            
        except sqlite3.Error as e:
            # DB级错误(连接/SQL/事务): 回滚 + 记"DB operation failed" — 小欧 2026-07-15
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    logger.warning(f"[db] rollback 失败: {db_name}")
            logger.error(f"DB operation failed [{db_name}]: {e}")
            raise
        except Exception as e:
            # 业务级异常(如FileExistsError): 仅回滚, 不当DB错误记避免误报; 由调用方(如execute_with_safety)记录 — 小欧 2026-07-15
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    logger.warning(f"[db] rollback 失败: {db_name}")
            raise
            
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    logger.warning(f"[db] 关闭连接失败: {db_name}")
    
    def init(self):
        """初始化所有数据库(应用启动时调用)"""
        import time as _time
        logger.info("Initializing all databases...")
        _ta = _time.time()
        init_chat_db(self.get_conn)
        logger.info(f"[启动耗时] init_chat_db: {_time.time()-_ta:.3f}s")
        _tb = _time.time()
        init_operations_db(self.get_conn)
        logger.info(f"[启动耗时] init_operations_db: {_time.time()-_tb:.3f}s")
        _tc = _time.time()
        init_task_tracker_db(self.get_conn)
        logger.info(f"[启动耗时] init_task_tracker_db: {_time.time()-_tc:.3f}s")
        logger.info(f"[启动耗时] db.init 合计: {_time.time()-_ta:.3f}s")
        logger.info("All databases initialized successfully")
    
    def init_observer(self):
        """初始化observer数据库(后续实现ToolObserver时调用)"""
        logger.info("Observer database initialized (placeholder)")


# 全局SDK实例(唯一入口)
db = DatabaseManager()
