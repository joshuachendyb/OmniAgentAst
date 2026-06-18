"""
Sankey报告模块 - 生成文件流向Sankey图数据
包含 generate_sankey_data
小沈 2026-05-29 拆分自 file_visualization.py
小欧 2026-06-18 DRY: 使用common.save_json_file替代_save_sankey_json
"""
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import asdict

from app.services.visualization.common import FlowData, save_json_file


def _query_sankey_operations(task_id: str) -> List[Tuple]:
    """查询Sankey操作记录 - 小沈 2026-06-08; 2026-06-17 改为调用service层"""
    from app.db.operation_queries import query_sankey_operations
    return query_sankey_operations(task_id)


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
        flows_dict = [asdict(f) for f in flows]
        save_json_file(flows_dict, output_path, logger_name="Sankey")
    
    return flows
