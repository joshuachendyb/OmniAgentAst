"""
文件操作安全服务 (File Operation Safety Service)
提供备份、回滚、操作历史等安全机制
"""
import os
import shutil
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import uuid4
import tempfile
import platform

from app.models.file_operations import (
    OperationRecord, SessionRecord, OperationType, OperationStatus,
    OperationRecordORM, SessionRecordORM
)
from app.utils.logger import logger


class FileSafetyConfig:
    """文件安全配置"""
    # 回收站路径
    RECYCLE_BIN_PATH: Path = Path.home() / ".omniagent" / "recycle_bin"
    # 数据库路径
    DB_PATH: Path = Path.home() / ".omniagent" / "operations.db"
    # 备份保留天数
    BACKUP_RETENTION_DAYS: int = 30
    # 报告输出路径
    REPORT_PATH: Path = Path.home() / ".omniagent" / "reports"
    
    @classmethod
    def ensure_directories(cls):
        """确保必要的目录存在"""
        cls.RECYCLE_BIN_PATH.mkdir(parents=True, exist_ok=True)
        cls.REPORT_PATH.mkdir(parents=True, exist_ok=True)


class FileOperationSafety:
    """
    文件操作安全服务
    
    功能：
    1. 操作历史记录 - 记录所有文件操作到SQLite数据库
    2. 回收站机制 - 删除的文件自动备份到回收站，30天后自动清理
    3. 文件映射 - 记录文件移动/重命名的源路径和目标路径
    4. 回滚功能 - 支持单个操作回滚和整个会话批量回滚
    """
    
    def __init__(self):
        self.config = FileSafetyConfig()
        self.config.ensure_directories()
        self._init_database()
        # 【修复-波次1】移除未使用的_connection属性
        # 所有方法都使用_get_connection()创建新连接，不需要保存连接引用
    
    def close(self):
        """
        关闭安全服务，清理资源
        
        【修复-波次1】添加资源清理方法，确保可以正确释放资源
        虽然当前实现每次操作都创建新连接，但为了未来扩展和完整性保留此方法
        """
        logger.info("FileOperationSafety resources cleaned up")
        
    def _init_database(self):
        """初始化SQLite数据库"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.config.DB_PATH))
            cursor = conn.cursor()
            
            # 创建操作记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    source_path TEXT,
                    destination_path TEXT,
                    backup_path TEXT,
                    backup_expires_at TIMESTAMP,
                    file_size INTEGER,
                    file_hash TEXT,
                    is_directory BOOLEAN DEFAULT 0,
                    file_extension TEXT,
                    duration_ms INTEGER,
                    space_impact_bytes INTEGER,
                    metadata TEXT DEFAULT '{}',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP,
                    rolled_back_at TIMESTAMP,
                    sequence_number INTEGER DEFAULT 0
                )
            ''')
            
            # 创建会话记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_operation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    agent_id TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    total_operations INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    rolled_back_count INTEGER DEFAULT 0,
                    report_generated BOOLEAN DEFAULT 0,
                    report_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_operations_session 
                ON file_operations(session_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_operations_created 
                ON file_operations(created_at)
            ''')
            
            conn.commit()
            logger.info("File operation database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
        finally:
            # 【修复问题8：数据库连接未关闭】
            # 确保连接总是被关闭，即使在异常情况下
            if conn:
                conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（线程安全）"""
        return sqlite3.connect(str(self.config.DB_PATH))
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件哈希（SHA-256）"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return ""
    
    def _backup_to_recycle_bin(self, source_path: Path) -> Optional[Path]:
        """
        将文件备份到回收站
        
        Args:
            source_path: 源文件路径
            
        Returns:
            备份路径，失败返回None
        """
        try:
            # 生成唯一的备份目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.config.RECYCLE_BIN_PATH / f"{timestamp}_{uuid4().hex[:8]}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 备份路径
            backup_path = backup_dir / source_path.name
            
            if source_path.is_dir():
                shutil.copytree(source_path, backup_path)
            else:
                shutil.copy2(source_path, backup_path)
            
            logger.info(f"File backed up to recycle bin: {source_path} -> {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup file to recycle bin: {e}")
            return None
    
    def record_operation(
        self,
        session_id: str,
        operation_type: OperationType,
        source_path: Optional[Path] = None,
        destination_path: Optional[Path] = None,
        sequence_number: int = 0,
        file_size: Optional[int] = None
    ) -> str:
        """
        记录文件操作（执行前）
        
        Args:
            session_id: 会话ID
            operation_type: 操作类型
            source_path: 源路径
            destination_path: 目标路径
            sequence_number: 操作顺序号
            file_size: 文件大小（字节）
            
        Returns:
            operation_id: 操作唯一标识符
        """
        operation_id = f"op-{uuid4().hex}"
        
        # 【修复】计算空间影响
        space_impact_bytes = None
        if file_size is not None:
            if operation_type == OperationType.CREATE:
                space_impact_bytes = -file_size  # 创建文件占用空间（负值）
            elif operation_type == OperationType.DELETE:
                space_impact_bytes = file_size   # 删除文件释放空间（正值）
        
        # 【修复-添加finally块确保资源释放】
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO file_operations 
                (operation_id, session_id, operation_type, status, source_path, 
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_id, session_id, operation_type.value, 
                OperationStatus.PENDING.value,
                str(source_path) if source_path else None,
                str(destination_path) if destination_path else None,
                sequence_number,
                file_size,
                space_impact_bytes,
                datetime.now()
            ))
            
            conn.commit()
            
            logger.debug(f"Operation recorded: {operation_id} - {operation_type.value}")
            return operation_id
            
        except Exception as e:
            logger.error(f"Failed to record operation: {e}")
            raise
            
        finally:
            if conn:
                conn.close()
    
    def execute_with_safety(
        self,
        operation_id: str,
        operation_func,
        *args,
        **kwargs
    ) -> bool:
        """
        安全执行文件操作（带备份和记录）
        
        Args:
            operation_id: 操作ID
            operation_func: 实际执行的操作函数
            *args, **kwargs: 传递给操作函数的参数
            
        Returns:
            是否执行成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取操作信息
            cursor.execute('''
                SELECT operation_type, source_path, destination_path 
                FROM file_operations WHERE operation_id = ?
            ''', (operation_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"Operation not found: {operation_id}")
                return False
            
            op_type, source_path_str, dest_path_str = row
            source_path = Path(source_path_str) if source_path_str else None
            dest_path = Path(dest_path_str) if dest_path_str else None
            
            # 更新状态为执行中
            cursor.execute('''
                UPDATE file_operations 
                SET status = ?, executed_at = ?
                WHERE operation_id = ?
            ''', (OperationStatus.EXECUTING.value, datetime.now(), operation_id))
            conn.commit()
            
            # 对于删除操作，先备份到回收站
            backup_path = None
            if op_type == OperationType.DELETE.value and source_path and source_path.exists():
                backup_path = self._backup_to_recycle_bin(source_path)
            
            # 执行实际操作
            success = operation_func(*args, **kwargs)
            
            if success:
                # 收集文件信息
                file_size = None
                file_hash = None
                file_extension = None
                
                if dest_path and dest_path.exists():
                    file_size = dest_path.stat().st_size
                    if dest_path.is_file():
                        file_hash = self._compute_file_hash(dest_path)
                        file_extension = dest_path.suffix.lower() if dest_path.suffix else None
                elif source_path and source_path.exists():
                    file_size = source_path.stat().st_size
                    if source_path.is_file():
                        file_hash = self._compute_file_hash(source_path)
                        file_extension = source_path.suffix.lower() if source_path.suffix else None
                
                # 计算操作耗时（毫秒）
                executed_at = datetime.now()
                cursor.execute('SELECT created_at FROM file_operations WHERE operation_id = ?', (operation_id,))
                created_at_row = cursor.fetchone()
                duration_ms = None
                if created_at_row and created_at_row[0]:
                    created_at = datetime.fromisoformat(created_at_row[0]) if isinstance(created_at_row[0], str) else created_at_row[0]
                    duration_ms = int((executed_at - created_at).total_seconds() * 1000)
                
                # 计算空间影响（字节）
                # DELETE: +size (frees space), CREATE: -size (uses space), MOVE/COPY: 0
                space_impact = 0
                if op_type == OperationType.DELETE.value and file_size:
                    space_impact = file_size  # Positive = freed space
                elif op_type == OperationType.CREATE.value and file_size:
                    space_impact = -file_size  # Negative = used space
                # MOVE and COPY have 0 net impact
                
                # 更新成功状态
                cursor.execute('''
                    UPDATE file_operations 
                    SET status = ?, backup_path = ?, backup_expires_at = ?,
                        file_size = ?, file_hash = ?, is_directory = ?,
                        file_extension = ?, duration_ms = ?, space_impact_bytes = ?,
                        executed_at = ?
                    WHERE operation_id = ?
                ''', (
                    OperationStatus.SUCCESS.value,
                    str(backup_path) if backup_path else None,
                    datetime.now() + timedelta(days=self.config.BACKUP_RETENTION_DAYS) if backup_path else None,
                    file_size,
                    file_hash,
                    1 if (source_path and source_path.is_dir()) or (dest_path and dest_path.is_dir()) else 0,
                    file_extension,
                    duration_ms,
                    space_impact,
                    executed_at,
                    operation_id
                ))
                
                logger.info(f"Operation executed successfully: {operation_id}")
            else:
                cursor.execute('''
                    UPDATE file_operations 
                    SET status = ?, error_message = ?
                    WHERE operation_id = ?
                ''', (OperationStatus.FAILED.value, "Operation failed", operation_id))
                
                logger.warning(f"Operation failed: {operation_id}")
            
            conn.commit()
            return success
            
        except Exception as e:
            logger.error(f"Error executing operation {operation_id}: {e}")
            cursor.execute('''
                UPDATE file_operations 
                SET status = ?, error_message = ?
                WHERE operation_id = ?
            ''', (OperationStatus.FAILED.value, str(e), operation_id))
            conn.commit()
            return False
        finally:
            conn.close()
    
    def rollback_operation(self, operation_id: str) -> bool:
        """
        回滚单个操作
        
        Args:
            operation_id: operation_id
            
        Returns:
            是否回滚成功
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
        
            cursor.execute('''
                SELECT operation_type, source_path, destination_path, backup_path, status
                FROM file_operations WHERE operation_id = ?
            ''', (operation_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"Operation not found for rollback: {operation_id}")
                return False
            
            op_type, src, dst, backup, status = row
            
            if status == OperationStatus.ROLLBACK.value:
                logger.info(f"Operation already rolled back: {operation_id}")
                return True
            
            success = False
            
            if op_type == OperationType.DELETE.value:
                # 回滚删除：从回收站恢复
                if backup and Path(backup).exists():
                    backup_path = Path(backup)
                    source_path = Path(src)
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, source_path)
                    else:
                        shutil.copy2(backup_path, source_path)
                    success = True
                    logger.info(f"Restored deleted file: {backup} -> {source_path}")
                    
            elif op_type == OperationType.MOVE.value:
                # 回滚移动：移回源位置
                dest_path = Path(dst)
                source_path = Path(src)
                if dest_path.exists():
                    dest_path.rename(source_path)
                    success = True
                    logger.info(f"Moved back: {dest_path} -> {source_path}")
                    
            elif op_type == OperationType.CREATE.value:
                # 回滚创建：删除创建的文件
                dest_path = Path(dst) if dst else Path(src)
                if dest_path.exists():
                    if dest_path.is_dir():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()
                    success = True
                    logger.info(f"Removed created file: {dest_path}")
            
            if success:
                cursor.execute('''
                    UPDATE file_operations 
                    SET status = ?, rolled_back_at = ?
                    WHERE operation_id = ?
                ''', (OperationStatus.ROLLBACK.value, datetime.now(), operation_id))
                conn.commit()
                logger.info(f"Operation rolled back: {operation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rollback operation {operation_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_operation_session_id(self, operation_id: str) -> Optional[str]:
        """
        获取操作对应的session_id
        
        Args:
            operation_id: 操作ID
            
        Returns:
            session_id，如果操作不存在返回None
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT session_id FROM file_operations WHERE operation_id = ?',
                (operation_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get session_id for operation {operation_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def rollback_session(self, session_id: str) -> Dict[str, Any]:
        """
        回滚整个会话的所有操作（按逆序）
        
        Args:
            session_id: 会话ID
            
        Returns:
            回滚结果统计
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            result = {
                "session_id": session_id,
                "total": 0,
                "success": 0,
                "failed": 0,
                "operations": []
            }
        
            # 获取会话的所有成功操作（按逆序）
            cursor.execute('''
                SELECT operation_id, operation_type, source_path, destination_path
                FROM file_operations 
                WHERE session_id = ? AND status = ?
                ORDER BY sequence_number DESC
            ''', (session_id, OperationStatus.SUCCESS.value))
            
            operations = cursor.fetchall()
            result["total"] = len(operations)
            
            for op_id, op_type, src, dst in operations:
                success = self.rollback_operation(op_id)
                result["operations"].append({
                    "operation_id": op_id,
                    "type": op_type,
                    "success": success
                })
                
                if success:
                    result["success"] += 1
                else:
                    result["failed"] += 1
            
            # 更新会话状态
            cursor.execute('''
                UPDATE file_operation_sessions 
                SET rolled_back_count = ?, status = ?
                WHERE session_id = ?
            ''', (result["success"], OperationStatus.ROLLBACK.value, session_id))
            conn.commit()
            
            logger.info(f"Session rollback completed: {session_id} - {result['success']}/{result['total']} succeeded")
            return result
            
        except Exception as e:
            logger.error(f"Failed to rollback session {session_id}: {e}")
            return result
        finally:
            conn.close()
    
    def get_session_operations(self, session_id: str) -> List[OperationRecord]:
        """
        获取会话的所有操作记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作记录列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM file_operations 
                WHERE session_id = ?
                ORDER BY sequence_number ASC
            ''', (session_id,))
            
            rows = cursor.fetchall()
            operations = []
            
            for row in rows:
                op = OperationRecord(
                    operation_id=row[1],
                    session_id=row[2],
                    operation_type=OperationType(row[3]),
                    status=OperationStatus(row[4]),
                    source_path=row[5],
                    destination_path=row[6],
                    backup_path=row[7],
                    backup_expires_at=row[8],
                    file_size=row[9],
                    file_hash=row[10],
                    is_directory=bool(row[11]),
                    file_extension=row[12],
                    duration_ms=row[13],
                    space_impact_bytes=row[14],
                    metadata=json.loads(row[15]) if row[15] else {},
                    error_message=row[16],
                    created_at=row[17],
                    executed_at=row[18],
                    rolled_back_at=row[19],
                    sequence_number=row[20]
                )
                operations.append(op)
            
            return operations
            
        except Exception as e:
            logger.error(f"Failed to get session operations: {e}")
            return []
        finally:
            conn.close()
    
    def get_operation(self, operation_id: str) -> Optional[OperationRecord]:
        """
        获取单个操作记录
        
        Args:
            operation_id: 操作ID
            
        Returns:
            操作记录，不存在返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM file_operations 
                WHERE operation_id = ?
            ''', (operation_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return OperationRecord(
                operation_id=row[1],
                session_id=row[2],
                operation_type=OperationType(row[3]),
                status=OperationStatus(row[4]),
                source_path=row[5],
                destination_path=row[6],
                backup_path=row[7],
                backup_expires_at=row[8],
                file_size=row[9],
                file_hash=row[10],
                is_directory=bool(row[11]),
                file_extension=row[12],
                duration_ms=row[13],
                space_impact_bytes=row[14],
                metadata=json.loads(row[15]) if row[15] else {},
                error_message=row[16],
                created_at=row[17],
                executed_at=row[18],
                rolled_back_at=row[19],
                sequence_number=row[20]
            )
            
        except Exception as e:
            logger.error(f"Failed to get operation {operation_id}: {e}")
            return None
        finally:
            conn.close()
    
    def cleanup_expired_backups(self) -> int:
        """
        清理过期的备份文件
        
        Returns:
            清理的文件数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        count = 0
        
        try:
            cursor.execute('''
                SELECT backup_path FROM file_operations 
                WHERE backup_expires_at < ? AND backup_path IS NOT NULL
            ''', (datetime.now(),))
            
            rows = cursor.fetchall()
            
            for (backup_path,) in rows:
                try:
                    path = Path(backup_path)
                    if path.exists():
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        count += 1
                        logger.info(f"Cleaned up expired backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup backup {backup_path}: {e}")
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired backups: {e}")
            return count
        finally:
            conn.close()


# 单例模式
_file_safety_instance: Optional[FileOperationSafety] = None


def get_file_safety_service() -> FileOperationSafety:
    """获取文件操作安全服务单例"""
    global _file_safety_instance
    if _file_safety_instance is None:
        _file_safety_instance = FileOperationSafety()
    return _file_safety_instance
