"""
文本报告模块 - 生成文本格式的文件操作报告
包含 build_text_report_lines + generate_text_report
小沈 2026-05-29 拆分自 file_visualization.py
"""
from typing import List, Dict, Tuple
from datetime import datetime

from app.utils.visualization.common import query_file_operations, count_op_stats, format_size
from app.utils.logger import logger


def build_text_report_lines(
    task_id: str, task_description: str,
    operations: List[Tuple], stats: Dict[str, int]
) -> List[str]:
    """构建文本报告的所有行（纯格式化，无 DB/IO 副作用）

    小沈 2026-05-25 重构拆分
    """
    lines = []
    lines.append("文件操作报告")
    lines.append("=" * 50)
    lines.append(f"会话ID: {task_id}")
    lines.append(f"Agent: file-operation-agent")
    lines.append(f"任务描述: {task_description}")
    lines.append(f"开始时间: {operations[0][6] if operations else ''}")
    lines.append(f"完成时间: 未完成")
    lines.append("")
    lines.append("-" * 80)
    lines.append("操作统计:")
    lines.append(f"  - 总操作数: {stats['total']}")
    lines.append(f"  - 成功: {stats['success']}")
    lines.append(f"  - 失败: {stats['failed']}")
    lines.append(f"  - 已回滚: {stats['rolled_back']}")
    lines.append("-" * 80)
    lines.append("")

    for i, (op_type, src, dst, status, size, is_dir, created_at, error) in enumerate(operations, 1):
        lines.append(f"[{i}] {op_type.upper()}")
        lines.append(f"    状态: {status}")
        if src:
            lines.append(f"    源路径: {src}")
        if dst:
            lines.append(f"    目标路径: {dst}")
        if size:
            lines.append(f"    文件大小: {format_size(size)}")
        if is_dir:
            lines.append(f"    类型: 目录")
        if error:
            lines.append(f"    错误信息: {error}")
        lines.append(f"    执行时间: {created_at}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("报告生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("=" * 80)
    return lines


def generate_text_report(task_id: str, task_description: str) -> str:
    """生成文本格式报告

    【小沈修改 2026-03-25】
    - 去掉 file_operation_sessions 表的依赖
    - task_description 作为参数传入
    - 统计数据从 file_operations 表计算

    【小沈修改 2026-04-30】
    - 修复列名：task_id → task_id（与 file_operations 表结构一致）

    【小沈重构 2026-05-25】
    - 重构拆分：提取 _query_file_operations / _count_op_stats / _build_text_report_lines

    Args:
        task_id: 任务ID
        task_description: 任务描述（用户消息）
        output_path: 输出路径（可选）

    Returns:
        报告文本内容
    """
    operations = query_file_operations(task_id)
    if not operations:
        logger.warning(f"No operations found for session: {task_id}")
        return ""

    stats = count_op_stats(operations)
    lines = build_text_report_lines(task_id, task_description, operations, stats)
    report_text = "\n".join(lines)

    # YAGNI 死代码：output_path 从未被实际传入，直接删除保存逻辑
    # 原 L157-161 已删除，调用方从未传 output_path

    return report_text
