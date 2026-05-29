"""
文件操作可视化服务 - 瘦入口模块
仅保留 get_visualizer + generate_all_reports，其他功能分散到子模块
小沈 2026-05-29 拆分重构
"""
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from app.utils.visualization.text_report import generate_text_report
from app.utils.visualization.tree_report import export_tree_to_json
from app.utils.visualization.sankey_report import generate_sankey_data
from app.utils.visualization.animation_report import generate_animation_script
from app.utils.logger import logger


class FileOperationVisualizer:
    """
    文件操作可视化服务（瘦入口，方法委托到子模块函数）

    功能：
    1. 文本列表 - 生成详细的文本报告
    2. 树形图 - 展示操作层级结构
    3. Sankey图 - 展示文件流向
    4. 动画报告 - 按时间顺序展示操作过程
    """

    def __init__(self):
        pass

    def generate_text_report(self, task_id: str, task_description: str) -> str:
        """生成文本格式报告（委托到 text_report 模块）"""
        return generate_text_report(task_id, task_description)

    def export_tree_to_json(self, task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
        """导出树形结构为JSON（委托到 tree_report 模块）"""
        return export_tree_to_json(task_id, task_description, output_path)

    def generate_sankey_data(self, task_id: str, output_path: Optional[Path] = None):
        """生成Sankey图数据（委托到 sankey_report 模块）"""
        return generate_sankey_data(task_id, output_path)

    def generate_animation_script(self, task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
        """生成动画展示脚本（委托到 animation_report 模块）"""
        return generate_animation_script(task_id, task_description, output_path)

    def generate_html_report(self, task_id: str, task_description: str) -> str:
        """生成HTML格式报告（委托到 html_report 模块）"""
        from app.utils.visualization.html_report import generate_html_report
        return generate_html_report(task_id, task_description)

    def generate_json_report(self, task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
        """生成JSON格式报告（委托到 json_report 模块）"""
        from app.utils.visualization.json_report import generate_json_report
        return generate_json_report(task_id, task_description, output_path)

    def generate_mermaid_report(self, task_id: str, output_path: Optional[Path] = None) -> str:
        """生成Mermaid格式报告（委托到 mermaid_report 模块）"""
        from app.utils.visualization.mermaid_report import generate_mermaid_report
        return generate_mermaid_report(task_id, output_path)

    def generate_tree_structure(self, task_id: str, task_description: str):
        """生成操作树形结构（委托到 tree_report 模块）"""
        from app.utils.visualization.tree_report import generate_tree_structure
        return generate_tree_structure(task_id, task_description)

    def generate_all_reports(self, task_id: str, task_description: str, output_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        生成所有类型的报告

        【小沈修改 2026-03-25】
        - 去掉 file_operation_sessions 表的依赖
        - task_description 作为参数传入

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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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


_visualizer_instance: Optional[FileOperationVisualizer] = None


def get_visualizer() -> FileOperationVisualizer:
    """获取可视化服务单例"""
    global _visualizer_instance
    if _visualizer_instance is None:
        _visualizer_instance = FileOperationVisualizer()
    return _visualizer_instance
