"""
可视化公共模块 - 数据类与共享工具函数
包含 OperationNode, FlowData 数据类及 count_op_stats, format_size, save_json_file

小沈 2026-05-29 拆分自 file_visualization.py
小沈 2026-06-17 删除db依赖,query_file_operations下沉到service层
"""
import json
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

from app.utils.logger import logger


@dataclass
class OperationNode:
    """操作节点(用于树形结构)"""
    id: str
    type: str
    name: str
    source: str = None
    destination: str = None
    status: str = "success"
    children: List['OperationNode'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class FlowData:
    """流程数据(用于Sankey图)"""
    source: str
    target: str
    value: int
    label: str


def count_op_stats(operations: List[Tuple]) -> Dict[str, int]:
    """统计操作状态分布,返回 {total, success, failed, rolled_back}

    小沈 2026-05-25 重构拆分
    小沈 2026-06-08 优化:从3次遍历改为1次遍历
    """
    success = 0
    failed = 0
    rolled_back = 0
    
    for op in operations:
        status = op[3]
        if status == "success":
            success += 1
        elif status == "failed":
            failed += 1
        if "rollback" in str(status):
            rolled_back += 1
    
    return {
        "total": len(operations),
        "success": success,
        "failed": failed,
        "rolled_back": rolled_back,
    }


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def save_json_file(data: dict, path: Path, logger_name: str = "report") -> str:
    """保存JSON到文件 - 小沈 2026-06-09 提取自 json_report/tree_report 的重复代码"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f"{logger_name} saved: {path}")
    return str(path)
