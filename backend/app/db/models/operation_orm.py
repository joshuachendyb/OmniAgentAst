"""
操作SQLAlchemy ORM模型 (Operation SQLAlchemy ORM)
用于SQLAlchemy数据库操作（当前未被使用，保留备用）

Author: 小沈 - 2026-05-22
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class OperationRecordORM(Base):
    """操作记录数据库表"""
    __tablename__ = 'file_operations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String(36), unique=True, nullable=False, index=True)
    task_id = Column(String(36), nullable=False, index=True)
    operation_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    
    source_path = Column(Text, nullable=True)
    destination_path = Column(Text, nullable=True)
    backup_path = Column(Text, nullable=True)
    backup_expires_at = Column(DateTime, nullable=True)
    
    file_size = Column(Integer, nullable=True)
    file_hash = Column(String(64), nullable=True)
    is_directory = Column(Boolean, default=False)
    file_extension = Column(String(20), nullable=True)
    
    # 可视化支持字段
    duration_ms = Column(Integer, nullable=True)
    space_impact_bytes = Column(Integer, nullable=True)
    
    operation_metadata = Column(Text, default='{}')  # JSON字符串
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    executed_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)
    
    sequence_number = Column(Integer, default=0)
    
    def to_pydantic(self):
        """转换为Pydantic模型"""
        from app.db.models.operation_models import OperationRecord
        import json
        return OperationRecord(
            id=self.id,
            operation_id=self.operation_id,
            task_id=self.task_id,
            operation_type=self.operation_type,
            status=self.status,
            source_path=self.source_path,
            destination_path=self.destination_path,
            backup_path=self.backup_path,
            backup_expires_at=self.backup_expires_at,
            file_size=self.file_size,
            file_hash=self.file_hash,
            is_directory=self.is_directory,
            file_extension=self.file_extension,
            duration_ms=self.duration_ms,
            space_impact_bytes=self.space_impact_bytes,
            metadata=json.loads(self.operation_metadata) if self.operation_metadata else {},
            error_message=self.error_message,
            created_at=self.created_at,
            executed_at=self.executed_at,
            rolled_back_at=self.rolled_back_at,
            sequence_number=self.sequence_number
        )
