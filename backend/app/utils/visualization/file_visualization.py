"""
文件操作可视化服务 (File Operation Visualization Service)
生成文本列表、树形图、Sankey图、动画报告
"""
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import textwrap
from jinja2 import Environment, FileSystemLoader

from app.services.safety.file.file_safety import FileSafetyConfig
from app.db import db
from app.utils.logger import logger


@dataclass
class OperationNode:
    """操作节点（用于树形结构）"""
    id: str
    type: str
    name: str
    source: Optional[str] = None
    destination: Optional[str] = None
    status: str = "success"
    children: List['OperationNode'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class FlowData:
    """流程数据（用于Sankey图）"""
    source: str
    target: str
    value: int
    label: str


class FileOperationVisualizer:
    """
    文件操作可视化服务
    
    功能：
    1. 文本列表 - 生成详细的文本报告
    2. 树形图 - 展示操作层级结构
    3. Sankey图 - 展示文件流向
    4. 动画报告 - 按时间顺序展示操作过程
    """
    
    def __init__(self):
        pass

    def _query_file_operations(self, task_id: str) -> List[Tuple]:
        """查询 file_operations 表，返回所有操作记录（与 generate_html_report 共享）

        小沈 2026-05-25 重构拆分
        """
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operation_type, source_path, destination_path, status,
                       file_size, is_directory, created_at, error_message
                FROM file_operations WHERE task_id = ?
                ORDER BY sequence_number ASC
            ''', (task_id,))
            operations = cursor.fetchall()
        return operations

    def _count_op_stats(self, operations: List[Tuple]) -> Dict[str, int]:
        """统计操作状态分布，返回 {total, success, failed, rolled_back}

        小沈 2026-05-25 重构拆分
        """
        return {
            "total": len(operations),
            "success": sum(1 for op in operations if op[3] == "success"),
            "failed": sum(1 for op in operations if op[3] == "failed"),
            "rolled_back": sum(1 for op in operations if "rollback" in str(op[3])),
        }

    def _build_text_report_lines(
        self, task_id: str, task_description: str,
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
                lines.append(f"    文件大小: {self._format_size(size)}")
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

    def generate_text_report(self, task_id: str, task_description: str) -> str:
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
        operations = self._query_file_operations(task_id)
        if not operations:
            logger.warning(f"No operations found for session: {task_id}")
            return ""

        stats = self._count_op_stats(operations)
        lines = self._build_text_report_lines(task_id, task_description, operations, stats)
        report_text = "\n".join(lines)

        # YAGNI 死代码：output_path 从未被实际传入，直接删除保存逻辑
        # 原 L157-161 已删除，调用方从未传 output_path

        return report_text
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def generate_tree_structure(self, task_id: str, task_description: str) -> OperationNode:
        """
        生成操作树形结构
        
        【小沈修改 2026-03-25】
        - 去掉 file_operation_sessions 表的依赖
        - task_description 作为参数传入
        
        Args:
            task_id: 会话ID
            task_description: 任务描述（用户消息）
            
        Returns:
            根节点
        """
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operation_id, operation_type, source_path, destination_path, status
                FROM file_operations WHERE task_id = ?
                ORDER BY sequence_number ASC
            ''', (task_id,))
            
            operations = cursor.fetchall()
        
        if not operations:
            return None
        
        root = OperationNode(
            id=task_id,
            type="session",
            name=task_description,  # 【小沈修改 2026-03-25】参数传入
            status="completed"  # 【小沈修改 2026-03-25】固定值，因为有操作记录
        )
        
        # 构建树形结构
        for op_id, op_type, src, dst, status in operations:
            node = OperationNode(
                id=op_id,
                type=op_type,
                name=Path(src).name if src else (Path(dst).name if dst else "unknown"),
                source=src,
                destination=dst,
                status=status
            )
            root.children.append(node)
        
        return root
    
    def export_tree_to_json(self, task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
        """
        导出树形结构为JSON
        
        【小沈修改 2026-03-25】
        - 新增 task_description 参数
        
        Args:
            task_id: 会话ID
            task_description: 任务描述（用户消息）
            output_path: 输出路径
            
        Returns:
            JSON字符串
        """
        root = self.generate_tree_structure(task_id, task_description)
        if not root:
            return "{}"
        
        def node_to_dict(node: OperationNode) -> dict:
            result = {
                "id": node.id,
                "type": node.type,
                "name": node.name,
                "status": node.status
            }
            if node.source:
                result["source"] = node.source
            if node.destination:
                result["destination"] = node.destination
            if node.children:
                result["children"] = [node_to_dict(child) for child in node.children]
            return result
        
        tree_dict = node_to_dict(root)
        json_str = json.dumps(tree_dict, ensure_ascii=False, indent=2)
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_str, encoding='utf-8')
            logger.info(f"Tree structure saved: {output_path}")
        
        return json_str
    
    def generate_sankey_data(self, task_id: str, output_path: Optional[Path] = None) -> List[FlowData]:
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
    
    def _query_animation_operations(self, task_id: str) -> List[Dict[str, Any]]:
        """查询指定task_id的文件操作记录（动画用）— 小健 2026-05-25

        使用场景:
        - generate_animation_script中查询操作历史

        使用示例:
            operations_data = self._query_animation_operations(task_id)

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

    @staticmethod
    def _build_animation_data(operations_data: List[Dict[str, Any]],
                             task_description: str) -> Dict[str, Any]:
        """从操作记录构建动画渲染所需的数据结构 — 小健 2026-05-25

        使用场景:
        - generate_animation_script中构建模板数据

        使用示例:
            anim_data = FileOperationVisualizer._build_animation_data(ops, desc)

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

    def _prepare_animation_data(self, anim_data: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """准备动画渲染所需数据 — 小健 2026-05-25

        使用场景:
            _render_animation_html中准备Jinja2模板变量

        使用示例:
            template_vars = self._prepare_animation_data(anim_data, task_id)

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

    def _load_template_assets(self) -> Tuple[str, str]:
        """加载CSS和JS模板资源 — 小健 2026-05-25

        使用场景:
            _render_animation_html中加载外部样式和脚本

        使用示例:
            css_content, js_content = self._load_template_assets()

        返回数据说明:
            - 返回Tuple[str, str]，分别是CSS内容和JS内容
        """
        template_dir = Path(__file__).parent / "templates"
        css_path = template_dir / "animation.css"
        js_path = template_dir / "animation.js"
        
        css_content = css_path.read_text(encoding="utf-8")
        js_content = js_path.read_text(encoding="utf-8")
        
        return css_content, js_content

    def _render_animation_html(self, anim_data: Dict[str, Any], task_id: str) -> str:
        """使用Jinja2模板渲染动画HTML — 小健 2026-05-25

        使用场景:
            generate_animation_script中渲染最终HTML

        使用示例:
            html = FileOperationVisualizer._render_animation_html(anim_data, task_id)

        返回数据说明:
            - 返回str，完整HTML文档字符串
        """
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(template_dir))
        
        template = env.get_template("animation.html")
        template_vars = self._prepare_animation_data(anim_data, task_id)
        css_content, js_content = self._load_template_assets()
        
        return template.render(
            **template_vars,
            css_content=css_content,
            js_content=js_content
        )

    def generate_animation_script(self, task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
        """
        生成动画展示脚本（HTML + JavaScript）— 小沈 2026-03-25, 2026-05-25 小健重构拆分

        Args:
            task_id: 会话ID
            task_description: 任务描述（用户消息）
            output_path: 输出路径

        Returns:
            HTML内容
        """
        operations_data = self._query_animation_operations(task_id)
        if not operations_data:
            logger.warning(f"No operations found for session: {task_id}")
            return ""

        anim_data = self._build_animation_data(operations_data, task_description)
        html_content = self._render_animation_html(anim_data, task_id)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding='utf-8')
            logger.info(f"Animation report saved: {output_path}")

        return html_content
    
    def generate_json_report(self, task_id: str, task_description: str, output_path: Optional[Path] = None) -> str:
        """
        生成JSON格式报告
        
        【小沈修改 2026-03-25】
        - 去掉 file_operation_sessions 表的依赖
        - task_description 作为参数传入
        
        Args:
            task_id: 会话ID
            task_description: 任务描述（用户消息）
            output_path: 输出路径
            
        Returns:
            JSON报告文件路径
        """
        # 【小沈修改 2026-03-25】直接获取操作记录，不依赖 file_operation_sessions 表
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operation_type, source_path, destination_path, status,
                       file_size, is_directory, created_at, error_message
                FROM file_operations WHERE task_id = ?
                ORDER BY sequence_number ASC
            ''', (task_id,))
            
            operations = cursor.fetchall()
        
        if not operations:
            logger.warning(f"No operations found for session: {task_id}")
            return ""
        
        # 【小沈修改 2026-03-25】统计数据从 operations 计算
        created_at = operations[0][6] if operations else None
        
        report_data = {
            "task_id": task_id,
            "agent_id": "file-operation-agent",  # 【小沈修改 2026-03-25】固定值
            "task_description": task_description,  # 【小沈修改 2026-03-25】参数传入
            "created_at": str(created_at) if created_at else None,
            "operations": []
        }
        
        for op_type, src, dst, status, size, is_dir, created_at, error in operations:
            op = {
                "type": op_type,
                "source": src,
                "destination": dst,
                "status": status,
                "file_size": size,
                "is_directory": bool(is_dir),
                "created_at": str(created_at) if created_at else None,
                "error_message": error
            }
            report_data["operations"].append(op)
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding='utf-8')
            logger.info(f"JSON report saved: {output_path}")
            return str(output_path)
        
        return json.dumps(report_data, ensure_ascii=False, indent=2)

    def _build_html_report_content(
        self, task_id: str, task_description: str,
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

    def generate_html_report(self, task_id: str, task_description: str) -> str:
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
        operations = self._query_file_operations(task_id)

        if not operations:
            logger.warning(f"No operations found for session: {task_id}")
            return ""

        op_types, status_counts = {}, {"success": 0, "failed": 0, "blocked": 0}
        for op in operations:
            op_types[op[0]] = op_types.get(op[0], 0) + 1
            if op[3] in status_counts:
                status_counts[op[3]] += 1

        html = self._build_html_report_content(task_id, task_description, operations, op_types, status_counts)

        # YAGNI 死代码：output_path 从未被实际传入，直接删除文件保存逻辑
        # 原 L854-859 已删除，调用方 generate_report 从未传 output_path

        return html
    
    def generate_mermaid_report(self, task_id: str, output_path: Optional[Path] = None) -> str:
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
        
        # 生成Mermaid流程图
        mermaid_content = "graph TD\n"
        mermaid_content += f"    Start([开始]) --> Op0\n"
        
        for i, (op_type, src, dst, status, seq) in enumerate(operations):
            node_id = f"Op{i}"
            next_node_id = f"Op{i+1}" if i < len(operations) - 1 else "End"
            
            # 节点标签
            if src and dst:
                label = f"{op_type}: {Path(src).name} → {Path(dst).name}"
            elif src:
                label = f"{op_type}: {Path(src).name}"
            elif dst:
                label = f"{op_type}: {Path(dst).name}"
            else:
                label = op_type
            
            # 状态样式
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
            output_dir = self.config.REPORT_PATH / task_id
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        reports = {}
        
        # 【小沈修改 2026-03-25】传递 task_description 给各个方法
        # 文本报告
        text_path = output_dir / f"report_text_{timestamp}.txt"
        self.generate_text_report(task_id, task_description)
        reports['text'] = text_path
        
        # 树形结构JSON
        tree_path = output_dir / f"report_tree_{timestamp}.json"
        self.export_tree_to_json(task_id, task_description, tree_path)
        reports['tree'] = tree_path
        
        # Sankey数据
        sankey_path = output_dir / f"report_sankey_{timestamp}.json"
        self.generate_sankey_data(task_id, sankey_path)
        reports['sankey'] = sankey_path
        
        # 动画报告
        animation_path = output_dir / f"report_animation_{timestamp}.html"
        self.generate_animation_script(task_id, task_description, animation_path)
        reports['animation'] = animation_path
        
        # 【小沈修改 2026-03-25】去掉 file_operation_sessions 表的更新
        # 因为不再依赖 file_operation_sessions 表
        
        logger.info(f"All reports generated for session {task_id}: {reports}")
        return reports


# 单例模式
_visualizer_instance: Optional[FileOperationVisualizer] = None


def get_visualizer() -> FileOperationVisualizer:
    """获取可视化服务单例"""
    global _visualizer_instance
    if _visualizer_instance is None:
        _visualizer_instance = FileOperationVisualizer()
    return _visualizer_instance
