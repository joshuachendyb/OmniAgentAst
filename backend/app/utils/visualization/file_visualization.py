"""
文件操作可视化服务 - 模块级函数入口

【10大原则规范 2026-05-30 小健】
- YAGNI: 去除 FileOperationVisualizer 类包装（10个方法8个是纯一行委托），改为模块级函数
- SRP: 每个报告类型独立模块，本文件仅做编排入口
- DRY: generate_all_reports 集中编排，各报告子模块函数直接复用
- KISS: 模块级函数而非类+单例，调用更直接
"""
from pathlib import Path
from typing import Dict, Optional

from app.utils.time_utils import timestamp_for_filename
from app.utils.visualization.text_report import generate_text_report
from app.utils.visualization.tree_report import export_tree_to_json
from app.utils.visualization.sankey_report import generate_sankey_data
from app.utils.visualization.animation_report import generate_animation_script
from app.utils.logger import logger


def generate_all_reports(task_id: str, task_description: str, output_dir: Optional[Path] = None) -> Dict[str, Path]:
    """
    生成所有类型的报告

    Args:
        task_id: 会话ID
        task_description: 任务描述（用户消息）
        output_dir: 输出目录

    Returns:
        报告文件路径字典
    """
    if output_dir is None:
        from app.services.safety.file.file_safety import FileSafetyConfig
        output_dir = FileSafetyConfig.REPORT_PATH / task_id

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timestamp_for_filename()

    reports = {}

    text_path = output_dir / f"report_text_{timestamp}.txt"
    generate_text_report(task_id, task_description)
    reports['text'] = text_path

    tree_path = output_dir / f"report_tree_{timestamp}.json"
    export_tree_to_json(task_id, task_description, tree_path)
    reports['tree'] = tree_path

    sankey_path = output_dir / f"report_sankey_{timestamp}.json"
    generate_sankey_data(task_id, sankey_path)
    reports['sankey'] = sankey_path

    animation_path = output_dir / f"report_animation_{timestamp}.html"
    generate_animation_script(task_id, task_description, animation_path)
    reports['animation'] = animation_path

    logger.info(f"All reports generated for session {task_id}: {reports}")
    return reports
