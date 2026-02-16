"""
文件操作记录模型 (File Operation Record Models)
SQLite数据表定义，用于记录所有文件操作的完整历史
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OperationType(str, Enum):
    """操作类型枚举"""
    CREATE = "create"          # 创建文件/目录
    DELETE = "delete"          # 删除文件/目录
    MOVE = "move"              # 移动文件/目录
    COPY = "copy"              # 复制文件/目录
    RENAME = "rename"          # 重命名文件/目录
    MODIFY = "modify"          # 修改文件内容


class OperationStatus(str, Enum):
    """操作状态枚举"""
    PENDING = "pending"        # 待执行
    EXECUTING = "executing"    # 执行中
    SUCCESS = "success"        # 成功
    FAILED = "failed"          # 失败
    ROLLBACK = "rollback"      # 已回滚


class OperationRecord(BaseModel):
    """
    文件操作记录模型
    记录每一次文件操作的完整信息，支持审计和回滚
    """
    # 基本信息
    id: Optional[int] = Field(default=None, description="数据库自增ID")
    operation_id: str = Field(..., description="唯一操作标识符 (UUID)")
    session_id: str = Field(..., description="所属会话ID")
    
    # 操作信息
    operation_type: OperationType = Field(..., description="操作类型")
    status: OperationStatus = Field(default=OperationStatus.PENDING, description="操作状态")
    
    # 路径信息
    source_path: Optional[str] = Field(default=None, description="源文件/目录路径")
    destination_path: Optional[str] = Field(default=None, description="目标文件/目录路径")
    
    # 备份信息（用于删除操作）
    backup_path: Optional[str] = Field(default=None, description="备份文件在回收站的路径")
    backup_expires_at: Optional[datetime] = Field(default=None, description="备份过期时间（默认30天）")
    
    # 文件元数据
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    file_hash: Optional[str] = Field(default=None, description="文件哈希（用于验证完整性）")
    is_directory: bool = Field(default=False, description="是否为目录")
    file_extension: Optional[str] = Field(default=None, description="文件扩展名（如.py, .txt）")
    
    # 可视化支持字段
    duration_ms: Optional[int] = Field(default=None, description="操作耗时（毫秒）")
    space_impact_bytes: Optional[int] = Field(default=None, description="空间影响（字节）：删除=+size, 创建=-size, 移动/复制=0")
    
    # 操作详情
    metadata: dict = Field(default_factory=dict, description="操作元数据（JSON格式）")
    error_message: Optional[str] = Field(default=None, description="错误信息（失败时）")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
    executed_at: Optional[datetime] = Field(default=None, description="操作执行时间")
    rolled_back_at: Optional[datetime] = Field(default=None, description="回滚时间")
    
    # 顺序信息（用于批量回滚）
    sequence_number: int = Field(default=0, description="会话内操作顺序号")
    
    class Config:
        json_schema_extra = {
            "example": {
                "operation_id": "op-123e4567-e89b-12d3-a456-426614174000",
                "session_id": "sess-abc-123",
                "operation_type": "move",
                "status": "success",
                "source_path": "C:\\Users\\test\\file.txt",
                "destination_path": "D:\\backup\\file.txt",
                "file_size": 1024,
                "is_directory": False,
                "sequence_number": 1
            }
        }


class SessionRecord(BaseModel):
    """
    会话记录模型
    记录一次完整的文件操作会话，包含多个操作记录
    """
    id: Optional[int] = Field(default=None, description="数据库自增ID")
    session_id: str = Field(..., description="唯一会话标识符 (UUID)")
    
    # 会话信息
    agent_id: str = Field(..., description="执行操作的Agent ID")
    task_description: str = Field(..., description="任务描述")
    
    # 状态
    status: OperationStatus = Field(default=OperationStatus.PENDING, description="会话状态")
    
    # 统计信息
    total_operations: int = Field(default=0, description="总操作数")
    success_count: int = Field(default=0, description="成功数")
    failed_count: int = Field(default=0, description="失败数")
    rolled_back_count: int = Field(default=0, description="已回滚数")
    
    # 可视化报告
    report_generated: bool = Field(default=False, description="是否已生成可视化报告")
    report_path: Optional[str] = Field(default=None, description="报告文件路径")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="会话开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="会话完成时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess-abc-123",
                "agent_id": "file-organizer",
                "task_description": "整理桌面文件",
                "status": "success",
                "total_operations": 5,
                "success_count": 5
            }
        }


# SQLAlchemy ORM模型（用于数据库操作）
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class OperationRecordORM(Base):
    """操作记录数据库表"""
    __tablename__ = 'file_operations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String(36), unique=True, nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)
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
    
    def to_pydantic(self) -> OperationRecord:
        """转换为Pydantic模型"""
        import json
        return OperationRecord(
            id=self.id,
            operation_id=self.operation_id,
            session_id=self.session_id,
            operation_type=OperationType(self.operation_type),
            status=OperationStatus(self.status),
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


class SessionRecordORM(Base):
    """会话记录数据库表"""
    __tablename__ = 'file_operation_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    
    agent_id = Column(String(100), nullable=False)
    task_description = Column(Text, nullable=False)
    
    status = Column(String(20), nullable=False, default='pending')
    
    total_operations = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    rolled_back_count = Column(Integer, default=0)
    
    report_generated = Column(Boolean, default=False)
    report_path = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    def to_pydantic(self) -> SessionRecord:
        """转换为Pydantic模型"""
        return SessionRecord(
            id=self.id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            task_description=self.task_description,
            status=OperationStatus(self.status),
            total_operations=self.total_operations,
            success_count=self.success_count,
            failed_count=self.failed_count,
            rolled_back_count=self.rolled_back_count,
            report_generated=self.report_generated,
            report_path=self.report_path,
            created_at=self.created_at,
            completed_at=self.completed_at
        )
