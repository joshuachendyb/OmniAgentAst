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

# 【小沈重构 2026-05-22】数据库配置迁移至 app/db/
from app.db.operations_db import get_connection
from app.db.config import OPERATIONS_DB_PATH
from app.db.models.operation_enums import OperationType, OperationStatus
from app.db.models.operation_models import OperationRecord, SessionRecord
from app.utils.logger import logger
from app.services.safety.manager import SafetyHook


class FileSafetyConfig:
    """文件安全配置"""
    # 回收站路径
    RECYCLE_BIN_PATH: Path = Path.home() / ".omniagent" / "recycle_bin"
    # 备份保留天数
    BACKUP_RETENTION_DAYS: int = 30
    # 报告输出路径
    # 【小沈修改 2026-03-25】Debug阶段改为项目目录下，方便查看
    # 生产环境可改为 Path.home() / ".omniagent" / "reports"
    PROJECT_ROOT = Path(__file__).resolve().parents[5]  # 项目根目录
    REPORT_PATH: Path = PROJECT_ROOT / "reports"
    
    @classmethod
    def ensure_directories(cls):
        """确保必要的目录存在"""
        cls.RECYCLE_BIN_PATH.mkdir(parents=True, exist_ok=True)
        cls.REPORT_PATH.mkdir(parents=True, exist_ok=True)


class FileOperationSafety(SafetyHook):
    """
    文件操作安全服务 — 继承SafetyHook，可注册到SafetyManager
    
    【重构 2026-05-27 小健】遵循DRY+OCP原则：
    - 继承SafetyHook基类，实现check()和execute_with_safety()
    - 可通过SafetyManager.register_hook("file", self)注册
    - SafetyManager.execute_with_safety("file", ...)统一调度
    
    功能：
    1. 操作历史记录 - 记录所有文件操作到SQLite数据库
    2. 回收站机制 - 删除的文件自动备份到回收站，30天后自动清理
    3. 文件映射 - 记录文件移动/重命名的源路径和目标路径
    4. 回滚功能 - 支持单个操作回滚和整个会话批量回滚
    """
    
    def __init__(self):
        self.config = FileSafetyConfig()
        self.config.ensure_directories()
        # 【小沈重构 2026-05-22】数据库初始化已由 app.db.operations_db 模块级调用
    
    def close(self):
        """
        关闭安全服务，清理资源
        
        【修复-波次1】添加资源清理方法，确保可以正确释放资源
        虽然当前实现每次操作都创建新连接，但为了未来扩展和完整性保留此方法
        """
        logger.info("FileOperationSafety resources cleaned up")
    
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
    
    @staticmethod
    def _row_to_operation_record(row) -> OperationRecord:
        """将SQLite行转换为OperationRecord - 小健 2026-05-24"""
        return OperationRecord(
            operation_id=row[1],
            task_id=row[2],
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
        # 【重要】task_id 用于操作追踪和回退，【禁止】使用 session_id
        # session_id 专用于会话场景，操作追踪必须用 task_id
        task_id: str,
        operation_type: Optional[str] = None,
        source_path: Optional[Path] = None,
        destination_path: Optional[Path] = None,
        sequence_number: int = 0,
        file_size: Optional[int] = None
    ) -> str:
        """
        记录文件操作（执行前）
        
        Args:
            task_id: 任务ID（操作追踪和回退用）
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
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO file_operations 
                (operation_id, task_id, operation_type, status, source_path, 
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_id, task_id, operation_type.value, 
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
    
    def _collect_file_info(self, path: Path) -> Dict[str, Any]:
        """收集文件信息（21.4 组件1，小沈 2026-05-25 实施）
        
        消除 F1a/F1b 双路径重复，is_directory 在此一并计算
        """
        if not path or not path.exists():
            return {"size": None, "hash": None, "extension": None, "is_directory": False}

        info = {
            "size": path.stat().st_size,
            "is_directory": path.is_dir(),
        }
        if path.is_file():
            info["hash"] = self._compute_file_hash(path)
            info["extension"] = path.suffix.lower() if path.suffix else None
        else:
            info["hash"] = None
            info["extension"] = None
        return info

    def _update_op_failed(self, cursor, operation_id: str, error_message: str):
        """统一更新 FAILED 状态（21.4 组件2，小沈 2026-05-25 实施）
        
        消除 3 处重复 UPDATE（O1b/E1b/X1a）
        """
        cursor.execute('''
            UPDATE file_operations 
            SET status = ?, error_message = ?
            WHERE operation_id = ?
        ''', (OperationStatus.FAILED.value, error_message, operation_id))

    def execute_with_safety(self, operation_id: str, operation_func, *args, **kwargs) -> bool:
        """安全执行文件操作（21.4 重构，小沈 2026-05-25 实施）"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT operation_type, source_path, destination_path, created_at
                FROM file_operations WHERE operation_id = ?
            ''', (operation_id,))
            row = cursor.fetchone()
            if not row:
                logger.error(f"Operation not found: {operation_id}")
                return False

            op_type, src_str, dst_str, created_at_str = row
            source_path = Path(src_str) if src_str else None
            dest_path = Path(dst_str) if dst_str else None
            created_at = datetime.fromisoformat(created_at_str) if isinstance(created_at_str, str) else created_at_str

            cursor.execute(
                'UPDATE file_operations SET status = ?, executed_at = ? WHERE operation_id = ?',
                (OperationStatus.EXECUTING.value, datetime.now(), operation_id),
            )
            conn.commit()

            backup_path = None
            if op_type == OperationType.DELETE.value and source_path and source_path.exists():
                backup_path = self._backup_to_recycle_bin(source_path)

            success = operation_func(*args, **kwargs)

            if success:
                target = dest_path if dest_path and dest_path.exists() else source_path if source_path and source_path.exists() else None
                info = self._collect_file_info(target) if target else {}

                executed_at = datetime.now()
                duration_ms = int((executed_at - created_at).total_seconds() * 1000) if created_at else None

                space_impact = 0
                if op_type == OperationType.DELETE.value and info.get("size"):
                    space_impact = info["size"]
                elif op_type == OperationType.CREATE.value and info.get("size"):
                    space_impact = -info["size"]

                cursor.execute('''
                    UPDATE file_operations SET status = ?, backup_path = ?, backup_expires_at = ?,
                        file_size = ?, file_hash = ?, is_directory = ?,
                        file_extension = ?, duration_ms = ?, space_impact_bytes = ?, executed_at = ?
                    WHERE operation_id = ?
                ''', (
                    OperationStatus.SUCCESS.value,
                    str(backup_path) if backup_path else None,
                    datetime.now() + timedelta(days=self.config.BACKUP_RETENTION_DAYS) if backup_path else None,
                    info.get("size"), info.get("hash"), info.get("is_directory", False),
                    info.get("extension"), duration_ms, space_impact, executed_at,
                    operation_id,
                ))
                logger.info(f"Operation executed successfully: {operation_id}")
            else:
                self._update_op_failed(cursor, operation_id, "Operation failed")

            conn.commit()
            return success

        except Exception as e:
            logger.error(f"Error executing operation {operation_id}: {e}")
            self._update_op_failed(cursor, operation_id, str(e))
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
            conn = get_connection()
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
    
    def get_operation_task_id(self, operation_id: str) -> Optional[str]:
        """
        获取操作对应的task_id
        
        Args:
            operation_id: 操作ID
            
        Returns:
            task_id，如果操作不存在返回None
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT task_id FROM file_operations WHERE operation_id = ?',
                (operation_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get task_id for operation {operation_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def rollback_session(self, task_id: str) -> Dict[str, Any]:
        """
        回滚整个会话的所有操作（按逆序）
        
        Args:
            task_id: 会话ID
            
        Returns:
            回滚结果统计
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            result = {
                "task_id": task_id,
                "total": 0,
                "success": 0,
                "failed": 0,
                "operations": []
            }
        
            # 获取会话的所有成功操作（按逆序）
            cursor.execute('''
                SELECT operation_id, operation_type, source_path, destination_path
                FROM file_operations 
                WHERE task_id = ? AND status = ?
                ORDER BY sequence_number DESC
            ''', (task_id, OperationStatus.SUCCESS.value))
            
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
                WHERE task_id = ?
            ''', (result["success"], OperationStatus.ROLLBACK.value, task_id))
            conn.commit()
            
            logger.info(f"Session rollback completed: {task_id} - {result['success']}/{result['total']} succeeded")
            return result
            
        except Exception as e:
            logger.error(f"Failed to rollback session {task_id}: {e}")
            return result
        finally:
            conn.close()
    
    def get_session_operations(self, task_id: str) -> List[OperationRecord]:
        """
        获取会话的所有操作记录
        
        Args:
            task_id: 会话ID
            
        Returns:
            操作记录列表
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM file_operations 
                WHERE task_id = ?
                ORDER BY sequence_number ASC
            ''', (task_id,))
            
            rows = cursor.fetchall()
            operations = [self._row_to_operation_record(row) for row in rows]
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
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM file_operations 
                WHERE operation_id = ?
            ''', (operation_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_operation_record(row)
            
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
        conn = get_connection()
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
