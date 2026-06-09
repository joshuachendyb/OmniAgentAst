"""
树形报告模块 - 生成操作树形结构及JSON导出
包含 generate_tree_structure + export_tree_to_json
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import List, Optional, Tuple

from app.utils.visualization.common import OperationNode
from app.db import db
from app.utils.logger import logger


def _query_tree_operations(task_id: str) -> List[Tuple]:
    """查询树形操作记录 - 小沈 2026-06-08"""
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_id, operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def _build_tree_nodes(task_id: str, task_description: str, operations: List[Tuple]) -> OperationNode:
    """构建树节点 - 小沈 2026-06-08"""
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


def _node_to_dict(node: OperationNode) -> dict:
    """节点转字典 - 小沈 2026-06-08"""
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
        result["children"] = [_node_to_dict(child) for child in node.children]
    return result


def _save_tree_json(tree_dict: dict, path: Path) -> None:
    """保存树形JSON到文件 - 小沈 2026-06-09 复用 common.save_json_file"""
    from app.utils.visualization.common import save_json_file as _save
    _save(tree_dict, path, logger_name="Tree structure")


def generate_tree_structure(task_id: str, task_description: str) -> OperationNode:
    """
    生成操作树形结构

    【小沈修改 2026-03-25】
    - 去掉 file_operation_sessions 表的依赖
    - task_description 作为参数传入

    Args:
        task_id: 会话ID
        task_description: 任务描述(用户消息)

    Returns:
        根节点
    """
    operations = _query_tree_operations(task_id)
    
    if not operations:
        return None
    
    return _build_tree_nodes(task_id, task_description, operations)


def export_tree_to_json(task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
    """
    导出树形结构为JSON

    【小沈修改 2026-03-25】
    - 新增 task_description 参数

    Args:
        task_id: 会话ID
        task_description: 任务描述(用户消息)
        output_path: 输出路径

    Returns:
        JSON字符串
    """
    root = generate_tree_structure(task_id, task_description)
    if not root:
        return "{}"

    tree_dict = _node_to_dict(root)
    json_str = json.dumps(tree_dict, ensure_ascii=False, indent=2)

    if output_path:
        _save_tree_json(tree_dict, output_path)

    return json_str
