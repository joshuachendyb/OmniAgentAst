"""
树形报告模块 - 生成操作树形结构及JSON导出
包含 generate_tree_structure + export_tree_to_json
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import Optional

from app.utils.visualization.common import OperationNode
from app.db import db
from app.utils.logger import logger


def generate_tree_structure(task_id: str, task_description: str) -> OperationNode:
    """
    生成操作树形结构

    【小沈修改 2026-03-25】
    - 去掉 file_operation_sessions 表的依赖
    - task_description 作为参数传入

    Args:
        task_id: 会话ID
        task_description: 任务描述（用户消息）

    Returns:
        根节点
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_id, operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))

        operations = cursor.fetchall()

    if not operations:
        return None

    root = OperationNode(
        id=task_id,
        type="session",
        name=task_description,
        status="completed"
    )

    for op_id, op_type, src, dst, status in operations:
        node = OperationNode(
            id=op_id,
            type=op_type,
            name=Path(src).name if src else (Path(dst).name if dst else "unknown"),
            source=src,
            destination=dst,
            status=status
        )
        root.children.append(node)

    return root


def export_tree_to_json(task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
    """
    导出树形结构为JSON

    【小沈修改 2026-03-25】
    - 新增 task_description 参数

    Args:
        task_id: 会话ID
        task_description: 任务描述（用户消息）
        output_path: 输出路径

    Returns:
        JSON字符串
    """
    root = generate_tree_structure(task_id, task_description)
    if not root:
        return "{}"

    def node_to_dict(node: OperationNode) -> dict:
        result = {
            "id": node.id,
            "type": node.type,
            "name": node.name,
            "status": node.status
        }
        if node.source:
            result["source"] = node.source
        if node.destination:
            result["destination"] = node.destination
        if node.children:
            result["children"] = [node_to_dict(child) for child in node.children]
        return result

    tree_dict = node_to_dict(root)
    json_str = json.dumps(tree_dict, ensure_ascii=False, indent=2)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str, encoding='utf-8')
        logger.info(f"Tree structure saved: {output_path}")

    return json_str
