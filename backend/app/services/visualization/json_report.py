"""
JSON报告模块 - 生成JSON格式的文件操作报告
包含 generate_json_report
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import List, Optional, Tuple

from app.utils.logger import logger



def _build_report_data(task_id: str, task_description: str, operations: List[Tuple]) -> dict:
    """构建报告数据 - 小沈 2026-06-08"""
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
    
    return report_data


def _save_json_file(data: dict, path: Path) -> str:
    """保存JSON到文件 - 小沈 2026-06-09 复用 common.save_json_file"""
    from app.services.visualization.common import save_json_file as _save
    return _save(data, path, logger_name="JSON report")


def generate_json_report(task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
    """
    生成JSON格式报告

    【小沈修改 2026-03-25】
    - 去掉 file_operation_sessions 表的依赖
    - task_description 作为参数传入

    Args:
        task_id: 会话ID
        task_description: 任务描述(用户消息)
        output_path: 输出路径

    Returns:
        JSON报告文件路径
    """
    from app.db.operation_queries import query_file_operations
    operations = query_file_operations(task_id)
    
    if not operations:
        logger.warning(f"No operations found for session: {task_id}")
        return ""
    
    report_data = _build_report_data(task_id, task_description, operations)
    
    if output_path:
        return _save_json_file(report_data, output_path)
    
    return json.dumps(report_data, ensure_ascii=False, indent=2)
