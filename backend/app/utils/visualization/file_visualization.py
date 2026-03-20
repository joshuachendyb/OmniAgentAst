"""
文件操作可视化服务 (File Operation Visualization Service)
生成文本列表、树形图、Sankey图、动画报告
"""
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import textwrap

from app.services.agent.safety import FileSafetyConfig
from app.services.agent import get_session_service
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
        self.config = FileSafetyConfig()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.config.DB_PATH))
    
    def generate_text_report(self, session_id: str, output_path: Optional[Path] = None) -> str:
        """
        生成文本格式报告
        
        Args:
            session_id: 会话ID
            output_path: 输出路径（可选）
            
        Returns:
            报告文本内容
        """
        session_service = get_session_service()
        session = session_service.get_session(session_id)
        
        if not session:
            logger.error(f"Session not found: {session_id}")
            return ""
        
        # 获取操作记录
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, 
                   file_size, is_directory, created_at, error_message
            FROM file_operations WHERE session_id = ?
            ORDER BY sequence_number ASC
        ''', (session_id,))
        
        operations = cursor.fetchall()
        conn.close()
        
        # 生成报告
        lines = []
        lines.append("=" * 80)
        lines.append("文件操作执行报告")
        lines.append("=" * 80)
        lines.append(f"")
        lines.append(f"会话ID: {session_id}")
        lines.append(f"Agent: {session.agent_id}")
        lines.append(f"任务描述: {session.task_description}")
        lines.append(f"开始时间: {session.created_at}")
        lines.append(f"完成时间: {session.completed_at or '未完成'}")
        lines.append(f"")
        lines.append("-" * 80)
        lines.append(f"操作统计:")
        lines.append(f"  - 总操作数: {session.total_operations}")
        lines.append(f"  - 成功: {session.success_count}")
        lines.append(f"  - 失败: {session.failed_count}")
        lines.append(f"  - 已回滚: {session.rolled_back_count}")
        lines.append("-" * 80)
        lines.append(f"")
        
        # 详细操作列表
        if operations:
            lines.append("详细操作记录:")
            lines.append("")
            
            for i, (op_type, src, dst, status, size, is_dir, created_at, error) in enumerate(operations, 1):
                lines.append(f"[{i}] {op_type.upper()}")
                lines.append(f"    状态: {status}")
                
                if src:
                    lines.append(f"    源路径: {src}")
                if dst:
                    lines.append(f"    目标路径: {dst}")
                
                if size:
                    size_str = self._format_size(size)
                    lines.append(f"    文件大小: {size_str}")
                
                if is_dir:
                    lines.append(f"    类型: 目录")
                
                if error:
                    lines.append(f"    错误信息: {error}")
                
                lines.append(f"    执行时间: {created_at}")
                lines.append("")
        
        lines.append("=" * 80)
        lines.append("报告生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("=" * 80)
        
        report_text = "\n".join(lines)
        
        # 保存到文件
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_text, encoding='utf-8')
            logger.info(f"Text report saved: {output_path}")
        
        return report_text
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def generate_tree_structure(self, session_id: str) -> OperationNode:
        """
        生成操作树形结构
        
        Args:
            session_id: 会话ID
            
        Returns:
            根节点
        """
        session_service = get_session_service()
        session = session_service.get_session(session_id)
        
        if not session:
            return None
        
        # 创建根节点
        root = OperationNode(
            id=session_id,
            type="session",
            name=session.task_description,
            status=session.status.value
        )
        
        # 获取操作记录
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_id, operation_type, source_path, destination_path, status
            FROM file_operations WHERE session_id = ?
            ORDER BY sequence_number ASC
        ''', (session_id,))
        
        operations = cursor.fetchall()
        conn.close()
        
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
    
    def export_tree_to_json(self, session_id: str, output_path: Optional[Path] = None) -> str:
        """
        导出树形结构为JSON
        
        Args:
            session_id: 会话ID
            output_path: 输出路径
            
        Returns:
            JSON字符串
        """
        root = self.generate_tree_structure(session_id)
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
    
    def generate_sankey_data(self, session_id: str, output_path: Optional[Path] = None) -> List[FlowData]:
        """
        生成Sankey图数据（文件流向图）
        
        Args:
            session_id: 会话ID
            output_path: 输出路径
            
        Returns:
            流程数据列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status
            FROM file_operations WHERE session_id = ? AND status = 'success'
            ORDER BY sequence_number ASC
        ''', (session_id,))
        
        operations = cursor.fetchall()
        conn.close()
        
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
    
    def generate_animation_script(self, session_id: str, output_path: Optional[Path] = None) -> str:
        """
        生成动画展示脚本（HTML + JavaScript）
        
        Args:
            session_id: 会话ID
            output_path: 输出路径
            
        Returns:
            HTML内容
        """
        session_service = get_session_service()
        session = session_service.get_session(session_id)
        
        if not session:
            return ""
        
        # 获取操作记录
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, created_at
            FROM file_operations WHERE session_id = ?
            ORDER BY sequence_number ASC
        ''', (session_id,))
        
        operations = cursor.fetchall()
        conn.close()
        
        # 构建操作序列数据
        operations_data = []
        for op_type, src, dst, status, created_at in operations:
            operations_data.append({
                "type": op_type,
                "source": src,
                "destination": dst,
                "status": status,
                "timestamp": created_at
            })
        
        # 生成HTML
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件操作动画报告 - {session.task_description}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.8; }}
        .controls {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            background: #667eea;
            color: white;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }}
        .btn:hover {{ background: #764ba2; transform: translateY(-2px); }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .progress-bar {{
            width: 100%;
            height: 4px;
            background: #333;
            border-radius: 2px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            width: 0%;
            transition: width 0.3s;
        }}
        .operations {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .operation {{
            padding: 15px;
            background: #16213e;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            opacity: 0.3;
            transform: translateX(-20px);
            transition: all 0.5s;
        }}
        .operation.active {{
            opacity: 1;
            transform: translateX(0);
            background: #1e3a5f;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}
        .operation.success {{ border-left-color: #4ade80; }}
        .operation.failed {{ border-left-color: #f87171; }}
        .operation-type {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .operation-path {{
            font-family: monospace;
            font-size: 12px;
            color: #aaa;
        }}
        .operation-arrow {{
            color: #667eea;
            margin: 0 10px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 30px;
        }}
        .stat-card {{
            padding: 15px;
            background: #16213e;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁 文件操作执行动画</h1>
            <p>{session.task_description}</p>
            <p style="margin-top: 10px; font-size: 12px;">会话ID: {session_id}</p>
        </div>
        
        <div class="controls">
            <button class="btn" id="playBtn" onclick="playAnimation()">▶️ 播放</button>
            <button class="btn" id="pauseBtn" onclick="pauseAnimation()" disabled>⏸️ 暂停</button>
            <button class="btn" onclick="resetAnimation()">🔄 重置</button>
            <button class="btn" onclick="exportReport()">📄 导出报告</button>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        
        <div class="operations" id="operations">
            <!-- Operations will be inserted here -->
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{session.total_operations}</div>
                <div class="stat-label">总操作数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{session.success_count}</div>
                <div class="stat-label">成功</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{session.failed_count}</div>
                <div class="stat-label">失败</div>
            </div>
        </div>
    </div>
    
    <script>
        const operations = {json.dumps(operations_data, ensure_ascii=False)};
        let currentIndex = 0;
        let isPlaying = false;
        let animationInterval = null;
        
        function renderOperations() {{
            const container = document.getElementById('operations');
            container.innerHTML = '';
            
            operations.forEach((op, index) => {{
                const div = document.createElement('div');
                div.className = `operation ${{op.status}}`;
                div.id = `op-${{index}}`;
                
                const typeMap = {{
                    'create': '📄 创建',
                    'delete': '🗑️ 删除',
                    'move': '📦 移动',
                    'copy': '📋 复制',
                    'rename': '✏️ 重命名',
                    'modify': '✏️ 修改'
                }};
                
                let pathHtml = '';
                if (op.source && op.destination) {{
                    pathHtml = `<span class="operation-path">${{op.source}}</span>
                               <span class="operation-arrow">→</span>
                               <span class="operation-path">${{op.destination}}</span>`;
                }} else if (op.source) {{
                    pathHtml = `<span class="operation-path">${{op.source}}</span>`;
                }} else if (op.destination) {{
                    pathHtml = `<span class="operation-path">${{op.destination}}</span>`;
                }}
                
                div.innerHTML = `
                    <div class="operation-type">${{typeMap[op.type] || op.type}}</div>
                    <div>${{pathHtml}}</div>
                `;
                
                container.appendChild(div);
            }});
        }}
        
        function updateProgress() {{
            const progress = (currentIndex / operations.length) * 100;
            document.getElementById('progressFill').style.width = progress + '%';
        }}
        
        function highlightOperation(index) {{
            // Remove active from all
            document.querySelectorAll('.operation').forEach(op => {{
                op.classList.remove('active');
            }});
            
            // Add active to current
            const current = document.getElementById(`op-${{index}}`);
            if (current) {{
                current.classList.add('active');
                current.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}
        
        function playAnimation() {{
            if (isPlaying) return;
            isPlaying = true;
            
            document.getElementById('playBtn').disabled = true;
            document.getElementById('pauseBtn').disabled = false;
            
            animationInterval = setInterval(() => {{
                if (currentIndex >= operations.length) {{
                    pauseAnimation();
                    return;
                }}
                
                highlightOperation(currentIndex);
                updateProgress();
                currentIndex++;
            }}, 1500); // 1.5 seconds per operation
        }}
        
        function pauseAnimation() {{
            isPlaying = false;
            clearInterval(animationInterval);
            
            document.getElementById('playBtn').disabled = false;
            document.getElementById('pauseBtn').disabled = true;
        }}
        
        function resetAnimation() {{
            pauseAnimation();
            currentIndex = 0;
            updateProgress();
            document.querySelectorAll('.operation').forEach(op => {{
                op.classList.remove('active');
            }});
        }}
        
        function exportReport() {{
            window.print();
        }}
        
        // Initialize
        renderOperations();
    </script>
</body>
</html>"""
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding='utf-8')
            logger.info(f"Animation report saved: {output_path}")
        
        return html_content
    
    def generate_all_reports(self, session_id: str, output_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        生成所有类型的报告
        
        Args:
            session_id: 会话ID
            output_dir: 输出目录
            
        Returns:
            报告文件路径字典
        """
        if output_dir is None:
            output_dir = self.config.REPORT_PATH / session_id
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        reports = {}
        
        # 文本报告
        text_path = output_dir / f"report_text_{timestamp}.txt"
        self.generate_text_report(session_id, text_path)
        reports['text'] = text_path
        
        # 树形结构JSON
        tree_path = output_dir / f"report_tree_{timestamp}.json"
        self.export_tree_to_json(session_id, tree_path)
        reports['tree'] = tree_path
        
        # Sankey数据
        sankey_path = output_dir / f"report_sankey_{timestamp}.json"
        self.generate_sankey_data(session_id, sankey_path)
        reports['sankey'] = sankey_path
        
        # 动画报告
        animation_path = output_dir / f"report_animation_{timestamp}.html"
        self.generate_animation_script(session_id, animation_path)
        reports['animation'] = animation_path
        
        # 更新会话记录
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE file_operation_sessions 
            SET report_generated = 1, report_path = ?
            WHERE session_id = ?
        ''', (str(output_dir), session_id))
        conn.commit()
        conn.close()
        
        logger.info(f"All reports generated for session {session_id}: {reports}")
        return reports


# 单例模式
_visualizer_instance: Optional[FileOperationVisualizer] = None


def get_visualizer() -> FileOperationVisualizer:
    """获取可视化服务单例"""
    global _visualizer_instance
    if _visualizer_instance is None:
        _visualizer_instance = FileOperationVisualizer()
    return _visualizer_instance
