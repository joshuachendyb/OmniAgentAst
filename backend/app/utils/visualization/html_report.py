"""
HTML报告模块 - 生成HTML格式的文件操作报告（含图表）
包含 build_html_report_content + generate_html_report
小沈 2026-05-29 拆分自 file_visualization.py
"""
from typing import List, Dict, Tuple

from app.utils.visualization.common import query_file_operations
from app.utils.logger import logger


def build_html_report_content(
    task_id: str, task_description: str,
    operations: List[Tuple], op_types: Dict[str, int],
    status_counts: Dict[str, int]
) -> str:
    """纯 HTML 模板渲染，不含任何 DB/IO 副作用

    小沈 2026-05-25 重构拆分
    """
    op_items = "".join(
        f'<div class="operation {s}"><strong>{t}</strong>'
        f'<p>源路径: {s2 or "N/A"}</p>'
        f'<p>目标路径: {d or "N/A"}</p>'
        f'<p>状态: {s}</p>'
        + (f'<p>错误: {e}</p>' if e else '') + '</div>'
        for t, s2, d, s, _sz, _isd, _ct, e in operations
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>文件操作报告 - {task_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
        .chart {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .operation {{ padding: 10px; margin: 5px 0; border-left: 3px solid #007bff; }}
        .operation.failed {{ border-left-color: #dc3545; }}
        .operation.blocked {{ border-left-color: #ffc107; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>文件操作执行报告</h1>
        <p>会话ID: {task_id}</p>
        <p>Agent: file-operation-agent</p>
        <p>任务: {task_description}</p>
    </div>

    <div class="chart">
        <h2>操作类型统计</h2>
        <ul>
            {"".join(f'<li>{op_type}: {count}次</li>' for op_type, count in op_types.items())}
        </ul>
    </div>

    <div class="chart">
        <h2>状态统计</h2>
        <ul>
            <li>成功: {status_counts['success']}次</li>
            <li>失败: {status_counts['failed']}次</li>
            <li>被阻止: {status_counts['blocked']}次</li>
        </ul>
    </div>

    <h2>操作详情</h2>
    {op_items}
</body>
</html>"""


def generate_html_report(task_id: str, task_description: str) -> str:
    """
    生成HTML格式报告（含图表）

    【小沈修改 2026-03-25】
    - 去掉 file_operation_sessions 表的依赖
    - task_description 作为参数传入

    【小沈重构 2026-05-25】
    - 重构拆分：DB 查询已共享（27.1），HTML 模板提取为 _build_html_report_content

    Args:
        task_id: 会话ID
        task_description: 任务描述（用户消息）
        output_path: 输出路径

    Returns:
        HTML报告文件路径
    """
    operations = query_file_operations(task_id)

    if not operations:
        logger.warning(f"No operations found for session: {task_id}")
        return ""

    op_types, status_counts = {}, {"success": 0, "failed": 0, "blocked": 0}
    for op in operations:
        op_types[op[0]] = op_types.get(op[0], 0) + 1
        if op[3] in status_counts:
            status_counts[op[3]] += 1

    html = build_html_report_content(task_id, task_description, operations, op_types, status_counts)

    # YAGNI 死代码：output_path 从未被实际传入，直接删除文件保存逻辑
    # 原 L854-859 已删除，调用方 generate_report 从未传 output_path

    return html
