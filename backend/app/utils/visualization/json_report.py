"""
JSON报告模块 - 生成JSON格式的文件操作报告
包含 generate_json_report
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import Optional

from app.db import db
from app.utils.logger import logger


def generate_json_report(task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
    """
    生成JSON格式报告

    【小沈修改 2026-03-25】
    - 去掉 file_operation_sessions 表的依赖
    - task_description 作为参数传入

    Args:
        task_id: 会话ID
        task_description: 任务描述（用户消息）
        output_path: 输出路径

    Returns:
        JSON报告文件路径
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status,
                   file_size, is_directory, created_at, error_message
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))

        operations = cursor.fetchall()

    if not operations:
        logger.warning(f"No operations found for session: {task_id}")
        return ""

    created_at = operations[0][6] if operations else None

    report_data = {
        "task_id": task_id,
        "agent_id": "file-operation-agent",
        "task_description": task_description,
        "created_at": str(created_at) if created_at else None,
        "operations": []
    }

    for op_type, src, dst, status, size, is_dir, created_at, error in operations:
        op = {
            "type": op_type,
            "source": src,
            "destination": dst,
            "status": status,
            "file_size": size,
            "is_directory": bool(is_dir),
            "created_at": str(created_at) if created_at else None,
            "error_message": error
        }
        report_data["operations"].append(op)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f"JSON report saved: {output_path}")
        return str(output_path)

    return json.dumps(report_data, ensure_ascii=False, indent=2)
