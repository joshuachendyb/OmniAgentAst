"""
Sankey报告模块 - 生成文件流向Sankey图数据
包含 generate_sankey_data
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import asdict

from app.utils.visualization.common import FlowData
from app.db import db
from app.utils.logger import logger


def _query_sankey_operations(task_id: str) -> List[Tuple]:
    """查询Sankey操作记录 - 小沈 2026-06-08"""
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ? AND status = 'success'
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def _build_flow_data(op_type: str, src: str, dst: str) -> Optional[FlowData]:
    """构建单个流程数据 - 小沈 2026-06-08"""
    if not src or not dst:
        return None
    
    src_dir = str(Path(src).parent)
    dst_dir = str(Path(dst).parent)
    
    if op_type == 'move':
        return FlowData(
            source=src_dir,
            target=dst_dir,
            value=1,
            label=f"{Path(src).name}"
        )
    elif op_type == 'copy':
        return FlowData(
            source=src_dir,
            target=dst_dir,
            value=1,
            label=f"copy: {Path(src).name}"
        )
    
    return None


def _build_sankey_flows(operations: List[Tuple]) -> List[FlowData]:
    """构建Sankey流程列表 - 小沈 2026-06-08"""
    flows = []
    for op_type, src, dst, status in operations:
        flow = _build_flow_data(op_type, src, dst)
        if flow:
            flows.append(flow)
    return flows


def _save_sankey_json(flows: List[FlowData], path: Path) -> None:
    """保存Sankey数据到文件 - 小沈 2026-06-08"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flows_dict = [asdict(f) for f in flows]
    path.write_text(json.dumps(flows_dict, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f"Sankey data saved: {path}")


def generate_sankey_data(task_id: str, output_path: Optional[Path] = None) -> List[FlowData]:
    """
    生成Sankey图数据(文件流向图)

    Args:
        task_id: 会话ID
        output_path: 输出路径

    Returns:
        流程数据列表
    """
    operations = _query_sankey_operations(task_id)
    flows = _build_sankey_flows(operations)
    
    if output_path:
        _save_sankey_json(flows, output_path)
    
    return flows
