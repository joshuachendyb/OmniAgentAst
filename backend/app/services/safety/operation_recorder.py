# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - record_operation 增 operation_id 可选参数, 操作ID生成统一交由 id_utils.generate_operation_id(DRY, 替代各处 f"op-{uuid4().hex}")
# 2026-07-18 - 小欧 - created_at 改 get_utc_timestamp() 入库 UTC Z, 消除 datetime.now() 裸传 sqlite3
"""
operation_recorder — 操作记录和文件信息收集

职责: 记录操作、更新操作状态、收集文件信息
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
from app.utils.id_utils import generate_operation_id  # 小欧 2026-07-16 统一ID生成(DRY)
from app.utils.time_utils import get_utc_timestamp  # 小欧 2026-07-18 时间统一入库

from app.db import db
from app.db.models.operation_models import OperationType, OperationStatus
from app.logger import logger
from app.services.safety.hash_helper import compute_file_hash


def collect_file_info(path: Path) -> Dict[str, Any]:
    """收集文件信息"""
    if not path or not path.exists():
        return {"size": None, "hash": None, "extension": None, "is_directory": False}
    info = {"size": path.stat().st_size, "is_directory": path.is_dir()}
    if path.is_file():
        info["hash"] = compute_file_hash(str(path))
        info["extension"] = path.suffix.lower() if path.suffix else None
    else:
        info["hash"] = None
        info["extension"] = None
    return info


def update_op_failed(cursor: sqlite3.Cursor, operation_id: str, error_message: str):
    """更新操作为失败状态"""
    cursor.execute(
        'UPDATE file_operations SET status = ?, error_message = ? WHERE operation_id = ?',
        (OperationStatus.FAILED.value, error_message, operation_id),
    )


def record_operation(
    task_id: str,
    operation_type: Optional[str] = None,
    source_path: Optional[Path] = None,
    destination_path: Optional[Path] = None,
    sequence_number: int = 0,
    file_size: Optional[int] = None,
    operation_id: Optional[str] = None,  # 小欧 2026-07-16 支持外部传入operation_id(贯通双表)
) -> Optional[str]:
    """记录文件操作到数据库（失败时返回None，不阻塞主流程）— 小健 2026-06-24 容错处理 — 小欧 2026-06-27 修复operation_type str/Enum不一致"""
    operation_id = operation_id or generate_operation_id()  # 小欧 2026-07-16 替代 f"op-{uuid4().hex}"
    space_impact_bytes = None
    try:
        if file_size is not None and operation_type is not None:
            if isinstance(operation_type, str):
                op_enum = OperationType(operation_type)
            else:
                op_enum = operation_type
            if op_enum == OperationType.CREATE:
                space_impact_bytes = -file_size
            elif op_enum == OperationType.DELETE:
                space_impact_bytes = file_size
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            op_type_str = operation_type.value if isinstance(operation_type, OperationType) else operation_type
            cursor.execute(
                '''INSERT INTO file_operations
                (operation_id, task_id, operation_type, status, source_path,
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (operation_id, task_id, op_type_str,
                  OperationStatus.PENDING.value,
                  str(source_path) if source_path else None,
                  str(destination_path) if destination_path else None,
                  sequence_number, file_size, space_impact_bytes, get_utc_timestamp()),
            )
        logger.debug(f"Operation recorded: {operation_id} - {op_type_str}")
        return operation_id
    except Exception as e:
        logger.warning(f"Failed to record operation: {e}, continue without recording")
        return None
