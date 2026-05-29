"""
Sankey报告模块 - 生成文件流向Sankey图数据
包含 generate_sankey_data
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict

from app.utils.visualization.common import FlowData
from app.db import db
from app.utils.logger import logger


def generate_sankey_data(task_id: str, output_path: Optional[Path] = None) -> List[FlowData]:
    """
    生成Sankey图数据（文件流向图）

    Args:
        task_id: 会话ID
        output_path: 输出路径

    Returns:
        流程数据列表
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ? AND status = 'success'
            ORDER BY sequence_number ASC
        ''', (task_id,))

        operations = cursor.fetchall()

    flows = []

    for op_type, src, dst, status in operations:
        if op_type == 'move' and src and dst:
            src_dir = str(Path(src).parent)
            dst_dir = str(Path(dst).parent)
            flows.append(FlowData(
                source=src_dir,
                target=dst_dir,
                value=1,
                label=f"{Path(src).name}"
            ))
        elif op_type == 'copy' and src and dst:
            src_dir = str(Path(src).parent)
            dst_dir = str(Path(dst).parent)
            flows.append(FlowData(
                source=src_dir,
                target=dst_dir,
                value=1,
                label=f"copy: {Path(src).name}"
            ))

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        flows_dict = [asdict(f) for f in flows]
        output_path.write_text(json.dumps(flows_dict, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f"Sankey data saved: {output_path}")

    return flows
