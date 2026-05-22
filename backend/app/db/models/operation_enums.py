"""
操作枚举类型 (Operation Enums)
定义文件操作类型和状态枚举

Author: 小沈 - 2026-05-22
"""
from enum import Enum


class OperationType(str, Enum):
    """操作类型枚举"""
    CREATE = "create"          # 创建文件/目录
    DELETE = "delete"          # 删除文件/目录
    MOVE = "move"              # 移动文件/目录
    COPY = "copy"              # 复制文件/目录
    RENAME = "rename"          # 重命名文件/目录
    MODIFY = "modify"          # 修改文件内容
    COMPARE = "compare"        # 比较文件
    BATCH_RENAME = "batch_rename"  # 批量重命名
    COMPRESS = "compress"      # 压缩文件
    MONITOR = "monitor"        # 监控文件
    STATISTICS = "statistics"  # 统计文件
    CHECKSUM = "checksum"      # 计算校验和


class OperationStatus(str, Enum):
    """操作状态枚举"""
    PENDING = "pending"        # 待执行
    EXECUTING = "executing"    # 执行中
    SUCCESS = "success"        # 成功
    FAILED = "failed"          # 失败
    ROLLBACK = "rollback"      # 已回滚
