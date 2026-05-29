"""
动画报告模块 - 生成文件操作动画展示脚本（HTML+JS）
包含 query_animation_operations, build_animation_data, prepare_animation_data,
     load_template_assets, render_animation_html, generate_animation_script
小沈 2026-05-29 拆分自 file_visualization.py
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from jinja2 import Environment, FileSystemLoader

from app.db import db
from app.utils.logger import logger


def query_animation_operations(task_id: str) -> List[Dict[str, Any]]:
    """查询指定task_id的文件操作记录（动画用）— 小健 2026-05-25

    使用场景:
    - generate_animation_script中查询操作历史

    使用示例:
        operations_data = query_animation_operations(task_id)

    返回数据说明:
    - 返回List[Dict[str, Any]]，每个元素包含type/source/destination/status/timestamp
    - 如果无操作记录，返回空列表
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, created_at
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        rows = cursor.fetchall()
    if not rows:
        return []
    return [
        {"type": op_type, "source": src, "destination": dst, "status": status, "timestamp": created_at}
        for op_type, src, dst, status, created_at in rows
    ]


def build_animation_data(operations_data: List[Dict[str, Any]],
                         task_description: str) -> Dict[str, Any]:
    """从操作记录构建动画渲染所需的数据结构 — 小健 2026-05-25

    使用场景:
    - generate_animation_script中构建模板数据

    使用示例:
        anim_data = build_animation_data(ops, desc)

    返回数据说明:
    - operations/task_description/total_operations/success_count/error_count/operation_types
    """
    success_count = sum(1 for op in operations_data if op.get("status") == "success")
    error_count = sum(1 for op in operations_data if op.get("status") != "success")
    operation_types: Dict[str, int] = {}
    for op in operations_data:
        op_type = op.get("type", "unknown")
        operation_types[op_type] = operation_types.get(op_type, 0) + 1
    return {
        "operations": operations_data,
        "task_description": task_description,
        "total_operations": len(operations_data),
        "success_count": success_count,
        "error_count": error_count,
        "operation_types": operation_types,
    }


def prepare_animation_data(anim_data: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    """准备动画渲染所需数据 — 小健 2026-05-25

    使用场景:
        render_animation_html中准备Jinja2模板变量

    使用示例:
        template_vars = prepare_animation_data(anim_data, task_id)

    返回数据说明:
        - 返回Dict，包含operations_json, task_description, total, success, error, task_id
    """
    return {
        "operations_json": json.dumps(anim_data["operations"], ensure_ascii=False),
        "task_description": anim_data["task_description"],
        "total": anim_data["total_operations"],
        "success": anim_data["success_count"],
        "error": anim_data["error_count"],
        "task_id": task_id
    }


def load_template_assets() -> Tuple[str, str]:
    """加载CSS和JS模板资源 — 小健 2026-05-25

    使用场景:
        render_animation_html中加载外部样式和脚本

    使用示例:
        css_content, js_content = load_template_assets()

    返回数据说明:
        - 返回Tuple[str, str]，分别是CSS内容和JS内容
    """
    template_dir = Path(__file__).parent / "templates"
    css_path = template_dir / "animation.css"
    js_path = template_dir / "animation.js"

    css_content = css_path.read_text(encoding="utf-8")
    js_content = js_path.read_text(encoding="utf-8")

    return css_content, js_content


def render_animation_html(anim_data: Dict[str, Any], task_id: str) -> str:
    """使用Jinja2模板渲染动画HTML — 小健 2026-05-25

    使用场景:
        generate_animation_script中渲染最终HTML

    使用示例:
        html = render_animation_html(anim_data, task_id)

    返回数据说明:
        - 返回str，完整HTML文档字符串
    """
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))

    template = env.get_template("animation.html")
    template_vars = prepare_animation_data(anim_data, task_id)
    css_content, js_content = load_template_assets()

    return template.render(
        **template_vars,
        css_content=css_content,
        js_content=js_content
    )


def generate_animation_script(task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
    """
    生成动画展示脚本（HTML + JavaScript）— 小沈 2026-03-25, 2026-05-25 小健重构拆分

    Args:
        task_id: 会话ID
        task_description: 任务描述（用户消息）
        output_path: 输出路径

    Returns:
        HTML内容
    """
    operations_data = query_animation_operations(task_id)
    if not operations_data:
        logger.warning(f"No operations found for session: {task_id}")
        return ""

    anim_data = build_animation_data(operations_data, task_description)
    html_content = render_animation_html(anim_data, task_id)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Animation report saved: {output_path}")

    return html_content
