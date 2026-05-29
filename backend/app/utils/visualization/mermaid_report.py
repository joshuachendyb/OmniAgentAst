"""
Mermaid报告模块 - 生成Mermaid格式流程图报告
包含 generate_mermaid_report
小沈 2026-05-29 拆分自 file_visualization.py
"""
from pathlib import Path
from typing import Optional

from app.db import db
from app.utils.logger import logger


def generate_mermaid_report(task_id: str, output_path: Optional[Path] = None) -> str:
    """
    生成Mermaid格式报告（流程图）

    Args:
        task_id: 会话ID
        output_path: 输出路径

    Returns:
        Mermaid报告文件路径
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, sequence_number
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))

        operations = cursor.fetchall()

    mermaid_content = "graph TD\n"
    mermaid_content += f"    Start([开始]) --> Op0\n"

    for i, (op_type, src, dst, status, seq) in enumerate(operations):
        node_id = f"Op{i}"
        next_node_id = f"Op{i+1}" if i < len(operations) - 1 else "End"

        if src and dst:
            label = f"{op_type}: {Path(src).name} → {Path(dst).name}"
        elif src:
            label = f"{op_type}: {Path(src).name}"
        elif dst:
            label = f"{op_type}: {Path(dst).name}"
        else:
            label = op_type

        if status == "success":
            style = ""
        elif status == "failed":
            style = ":::failed"
        else:
            style = ":::blocked"

        mermaid_content += f"    {node_id}[{label}]{style} --> {next_node_id}\n"

    mermaid_content += f"    Op{len(operations)-1} --> End([结束])\n"
    mermaid_content += "\n"
    mermaid_content += "classDef failed fill:#ffcccc,stroke:#dc3545\n"
    mermaid_content += "classDef blocked fill:#fff3cd,stroke:#ffc107\n"

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(mermaid_content, encoding='utf-8')
        logger.info(f"Mermaid report saved: {output_path}")
        return str(output_path)

    return mermaid_content
