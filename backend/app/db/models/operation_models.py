"""
操作数据模型 (Operation Data Models)
定义文件操作记录和任务记录的数据结构
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正

Author: 小沈 - 2026-05-22
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.db.models.operation_enums import OperationType, OperationStatus


class OperationRecord(BaseModel):
    """
    文件操作记录模型
    记录每一次文件操作的完整信息，支持审计和回滚
    """
    # 基本信息
    id: Optional[int] = Field(default=None, description="数据库自增ID")
    operation_id: str = Field(..., description="唯一操作标识符 (UUID)")
    task_id: str = Field(..., description="任务执行ID")
    
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
    sequence_number: int = Field(default=0, description="任务内操作顺序号")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation_id": "op-123e4567-e89b-12d3-a456-426614174000",
                "task_id": "task-abc-123",
                "operation_type": "move",
                "status": "success",
                "source_path": "C:\\Users\\test\\file.txt",
                "destination_path": "D:\\backup\\file.txt",
                "file_size": 1024,
                "is_directory": False,
                "sequence_number": 1
            }
        }
    )


class TaskRecord(BaseModel):
    """
    任务记录模型
    记录一次完整的文件操作任务，包含多个操作记录
    """
    id: Optional[int] = Field(default=None, description="数据库自增ID")
    task_id: str = Field(..., description="任务执行ID (UUID)")
    
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
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "task-abc-123",
                "agent_id": "file-organizer",
                "task_description": "整理桌面文件",
                "status": "success",
                "total_operations": 5,
                "success_count": 5
            }
        }
    )
