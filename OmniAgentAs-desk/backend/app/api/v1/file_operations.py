"""
文件操作API路由 (File Operations API Routes)
提供操作历史查询、可视化数据、报告生成和回滚功能
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.file_operations import OperationRecord, OperationType, OperationStatus
from app.services.file_operations import (
    get_file_safety_service,
    get_session_service,
    FileTools
)
from app.utils.visualization import get_visualizer
from app.utils.logger import logger

router = APIRouter()


# ============ 响应模型 ============

class TreeNode(BaseModel):
    """树形结构节点"""
    name: str = Field(..., description="节点名称（文件名或目录名）")
    path: str = Field(..., description="完整路径")
    type: str = Field(..., description="类型: file, directory, operation")
    operation_type: Optional[str] = Field(None, description="操作类型")
    status: Optional[str] = Field(None, description="操作状态")
    file_size: Optional[int] = Field(None, description="文件大小")
    file_extension: Optional[str] = Field(None, description="文件扩展名")
    duration_ms: Optional[int] = Field(None, description="操作耗时")
    space_impact_bytes: Optional[int] = Field(None, description="空间影响")
    children: List['TreeNode'] = Field(default_factory=list, description="子节点")
    timestamp: Optional[str] = Field(None, description="操作时间戳")

TreeNode.update_forward_refs()


class FlowData(BaseModel):
    """流向数据（桑基图）"""
    nodes: List[Dict[str, Any]] = Field(..., description="节点列表")
    links: List[Dict[str, Any]] = Field(..., description="连接列表")
    statistics: Dict[str, Any] = Field(..., description="统计信息")


class StatsData(BaseModel):
    """统计摘要数据"""
    total_operations: int = Field(..., description="总操作数")
    operations_by_type: Dict[str, int] = Field(..., description="按类型统计")
    operations_by_extension: Dict[str, int] = Field(..., description="按扩展名统计")
    total_space_impact: int = Field(..., description="总空间影响")
    total_duration_ms: int = Field(..., description="总耗时")
    success_rate: float = Field(..., description="成功率")
    average_duration_ms: float = Field(..., description="平均耗时")
    largest_files: List[Dict[str, Any]] = Field(..., description="最大文件")


class AnimationFrame(BaseModel):
    """动画帧数据"""
    frame_index: int = Field(..., description="帧序号")
    timestamp: str = Field(..., description="时间戳")
    operation: Dict[str, Any] = Field(..., description="操作信息")
    current_state: Dict[str, Any] = Field(..., description="当前状态")


class AnimationData(BaseModel):
    """动画数据"""
    frames: List[AnimationFrame] = Field(..., description="帧列表")
    total_frames: int = Field(..., description="总帧数")
    total_duration_ms: int = Field(..., description="总时长")
    metadata: Dict[str, Any] = Field(..., description="元数据")


class ReportResponse(BaseModel):
    """报告响应"""
    success: bool = Field(..., description="是否成功")
    format: str = Field(..., description="报告格式")
    content: Optional[str] = Field(None, description="报告内容（文本格式）")
    data: Optional[Dict[str, Any]] = Field(None, description="报告数据（JSON格式）")
    download_url: Optional[str] = Field(None, description="下载链接（HTML格式）")
    message: Optional[str] = Field(None, description="消息")


class RollbackRequest(BaseModel):
    """回滚请求"""
    operation_id: Optional[str] = Field(None, description="操作ID（不传则回滚整个会话）")


class RollbackResponse(BaseModel):
    """回滚响应"""
    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="会话ID")
    total_operations: int = Field(..., description="总操作数")
    success_count: int = Field(..., description="成功回滚数")
    failed_count: int = Field(..., description="失败数")
    operations: List[Dict[str, Any]] = Field(..., description="操作详情")


class OperationsListResponse(BaseModel):
    """操作列表响应"""
    session_id: str = Field(..., description="会话ID")
    total: int = Field(..., description="总数")
    operations: List[OperationRecord] = Field(..., description="操作记录列表")


# ============ API端点 ============

@router.get("/operations", response_model=OperationsListResponse)
async def list_operations(
    session_id: str = Query(..., description="会话ID"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制")
):
    """
    获取会话的所有操作记录
    
    - **session_id**: 会话ID
    - **limit**: 最多返回多少条记录
    """
    try:
        safety = get_file_safety_service()
        operations = safety.get_session_operations(session_id)
        
        # 限制数量
        operations = operations[:limit]
        
        return OperationsListResponse(
            session_id=session_id,
            total=len(operations),
            operations=operations
        )
        
    except Exception as e:
        logger.error(f"Failed to list operations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/tree-data")
async def get_tree_data(
    session_id: str = Query(..., description="会话ID")
) -> Dict[str, Any]:
    """
    获取树形结构数据
    
    用于前端D3.js/ECharts渲染树形可视化
    
    - **session_id**: 会话ID
    
    返回嵌套的树形JSON结构
    """
    try:
        safety = get_file_safety_service()
        visualizer = get_visualizer()
        
        operations = safety.get_session_operations(session_id)
        
        if not operations:
            return {"root": None, "operations_count": 0}
        
        # 构建树形结构
        tree_data = visualizer.build_tree_structure(operations)
        
        return {
            "root": tree_data,
            "operations_count": len(operations),
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get tree data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/flow-data")
async def get_flow_data(
    session_id: str = Query(..., description="会话ID")
) -> FlowData:
    """
    获取流向数据（桑基图）
    
    用于前端D3.js/ECharts渲染桑基图
    
    - **session_id**: 会话ID
    
    返回节点和连接的列表，适合桑基图可视化
    """
    try:
        safety = get_file_safety_service()
        operations = safety.get_session_operations(session_id)
        
        if not operations:
            return FlowData(nodes=[], links=[], statistics={})
        
        # 构建节点列表
        nodes = []
        node_indices = {}
        
        # 添加源目录和目标目录作为节点
        for op in operations:
            if op.source_path and op.source_path not in node_indices:
                node_indices[op.source_path] = len(nodes)
                nodes.append({
                    "id": len(nodes),
                    "name": Path(op.source_path).name or op.source_path,
                    "path": op.source_path,
                    "type": "directory" if op.is_directory else "file"
                })
            
            if op.destination_path and op.destination_path not in node_indices:
                node_indices[op.destination_path] = len(nodes)
                nodes.append({
                    "id": len(nodes),
                    "name": Path(op.destination_path).name or op.destination_path,
                    "path": op.destination_path,
                    "type": "directory" if op.is_directory else "file"
                })
        
        # 构建连接列表
        links = []
        for op in operations:
            if op.source_path and op.destination_path:
                source_idx = node_indices.get(op.source_path)
                target_idx = node_indices.get(op.destination_path)
                
                if source_idx is not None and target_idx is not None:
                    links.append({
                        "source": source_idx,
                        "target": target_idx,
                        "value": op.file_size or 0,
                        "operation_type": op.operation_type.value,
                        "operation_id": op.operation_id,
                        "duration_ms": op.duration_ms
                    })
        
        # 统计信息
        stats = {
            "total_nodes": len(nodes),
            "total_links": len(links),
            "total_operations": len(operations),
            "operations_by_type": {}
        }
        
        for op in operations:
            op_type = op.operation_type.value
            stats["operations_by_type"][op_type] = stats["operations_by_type"].get(op_type, 0) + 1
        
        return FlowData(nodes=nodes, links=links, statistics=stats)
        
    except Exception as e:
        logger.error(f"Failed to get flow data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/stats-data")
async def get_stats_data(
    session_id: str = Query(..., description="会话ID")
) -> StatsData:
    """
    获取统计摘要数据
    
    用于前端仪表盘和数据可视化
    
    - **session_id**: 会话ID
    
    返回操作统计、按类型分组、空间影响等
    """
    try:
        safety = get_file_safety_service()
        operations = safety.get_session_operations(session_id)
        
        if not operations:
            return StatsData(
                total_operations=0,
                operations_by_type={},
                operations_by_extension={},
                total_space_impact=0,
                total_duration_ms=0,
                success_rate=0.0,
                average_duration_ms=0.0,
                largest_files=[]
            )
        
        # 按类型统计
        operations_by_type = {}
        for op in operations:
            op_type = op.operation_type.value
            operations_by_type[op_type] = operations_by_type.get(op_type, 0) + 1
        
        # 按扩展名统计
        operations_by_extension = {}
        for op in operations:
            ext = op.file_extension or "no_extension"
            operations_by_extension[ext] = operations_by_extension.get(ext, 0) + 1
        
        # 总空间影响
        total_space_impact = sum(
            op.space_impact_bytes or 0 for op in operations
        )
        
        # 总耗时
        total_duration_ms = sum(
            op.duration_ms or 0 for op in operations
        )
        
        # 成功率
        success_count = sum(
            1 for op in operations if op.status == OperationStatus.SUCCESS
        )
        success_rate = success_count / len(operations) * 100 if operations else 0.0
        
        # 平均耗时
        average_duration_ms = total_duration_ms / len(operations) if operations else 0.0
        
        # 最大文件
        largest_files = sorted(
            [
                {
                    "operation_id": op.operation_id,
                    "path": op.source_path or op.destination_path,
                    "size": op.file_size,
                    "extension": op.file_extension
                }
                for op in operations if op.file_size
            ],
            key=lambda x: x["size"],
            reverse=True
        )[:10]  # Top 10
        
        return StatsData(
            total_operations=len(operations),
            operations_by_type=operations_by_type,
            operations_by_extension=operations_by_extension,
            total_space_impact=total_space_impact,
            total_duration_ms=total_duration_ms,
            success_rate=round(success_rate, 2),
            average_duration_ms=round(average_duration_ms, 2),
            largest_files=largest_files
        )
        
    except Exception as e:
        logger.error(f"Failed to get stats data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/animation-data")
async def get_animation_data(
    session_id: str = Query(..., description="会话ID"),
    frame_interval_ms: int = Query(1000, ge=100, le=10000, description="每帧间隔毫秒")
) -> AnimationData:
    """
    获取动画帧数据
    
    用于前端渲染操作过程动画
    
    - **session_id**: 会话ID
    - **frame_interval_ms**: 每帧之间的间隔时间（毫秒）
    
    返回按时间排序的动画帧序列
    """
    try:
        safety = get_file_safety_service()
        operations = safety.get_session_operations(session_id)
        
        if not operations:
            return AnimationData(
                frames=[],
                total_frames=0,
                total_duration_ms=0,
                metadata={"session_id": session_id}
            )
        
        # 按执行时间排序
        sorted_ops = sorted(
            operations,
            key=lambda x: x.executed_at or x.created_at
        )
        
        frames = []
        cumulative_time = 0
        
        for idx, op in enumerate(sorted_ops):
            frame_duration = op.duration_ms or frame_interval_ms
            cumulative_time += frame_duration
            
            frame = AnimationFrame(
                frame_index=idx,
                timestamp=(op.executed_at or op.created_at).isoformat() if op.executed_at or op.created_at else "",
                operation={
                    "operation_id": op.operation_id,
                    "type": op.operation_type.value,
                    "source_path": op.source_path,
                    "destination_path": op.destination_path,
                    "file_size": op.file_size,
                    "file_extension": op.file_extension,
                    "duration_ms": op.duration_ms,
                    "space_impact_bytes": op.space_impact_bytes,
                    "status": op.status.value
                },
                current_state={
                    "total_operations_so_far": idx + 1,
                    "cumulative_duration_ms": cumulative_time,
                    "cumulative_space_impact": sum(
                        o.space_impact_bytes or 0 for o in sorted_ops[:idx+1]
                    )
                }
            )
            frames.append(frame)
        
        return AnimationData(
            frames=frames,
            total_frames=len(frames),
            total_duration_ms=cumulative_time,
            metadata={
                "session_id": session_id,
                "frame_interval_ms": frame_interval_ms,
                "operations_count": len(operations)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get animation data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/report")
async def generate_report(
    session_id: str = Query(..., description="会话ID"),
    format: Literal["txt", "json", "html", "mmd"] = Query("json", description="报告格式")
) -> ReportResponse:
    """
    生成操作报告
    
    - **session_id**: 会话ID
    - **format**: 报告格式
        - txt: 文本报告
        - json: JSON格式数据
        - html: HTML可视化报告（独立文件）
        - mmd: Mermaid流程图
    
    返回报告内容或下载链接
    """
    try:
        visualizer = get_visualizer()
        
        if format == "txt":
            report_path = visualizer.generate_text_report(session_id)
            if report_path and Path(report_path).exists():
                content = Path(report_path).read_text(encoding="utf-8")
                return ReportResponse(
                    success=True,
                    format="txt",
                    content=content,
                    message="Text report generated successfully"
                )
            else:
                return ReportResponse(
                    success=False,
                    format="txt",
                    message="Failed to generate text report"
                )
        
        elif format == "json":
            report_path = visualizer.generate_json_report(session_id)
            if report_path and Path(report_path).exists():
                import json
                data = json.loads(Path(report_path).read_text(encoding="utf-8"))
                return ReportResponse(
                    success=True,
                    format="json",
                    data=data,
                    message="JSON report generated successfully"
                )
            else:
                return ReportResponse(
                    success=False,
                    format="json",
                    message="Failed to generate JSON report"
                )
        
        elif format == "html":
            report_path = visualizer.generate_html_report(session_id)
            if report_path and Path(report_path).exists():
                # 返回文件URL（相对于报告目录）
                relative_path = Path(report_path).name
                return ReportResponse(
                    success=True,
                    format="html",
                    download_url=f"/static/reports/{relative_path}",
                    message="HTML report generated successfully"
                )
            else:
                return ReportResponse(
                    success=False,
                    format="html",
                    message="Failed to generate HTML report"
                )
        
        elif format == "mmd":
            report_path = visualizer.generate_mermaid_report(session_id)
            if report_path and Path(report_path).exists():
                content = Path(report_path).read_text(encoding="utf-8")
                return ReportResponse(
                    success=True,
                    format="mmd",
                    content=content,
                    message="Mermaid diagram generated successfully"
                )
            else:
                return ReportResponse(
                    success=False,
                    format="mmd",
                    message="Failed to generate Mermaid diagram"
                )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/operations/rollback", response_model=RollbackResponse)
async def rollback_operations(request: RollbackRequest):
    """
    回滚操作
    
    - **operation_id**: 操作ID（可选，不传则回滚整个会话）
    - **session_id**: 会话ID（从请求头或参数获取）
    
    回滚指定的操作或整个会话的所有操作
    """
    try:
        safety = get_file_safety_service()
        
        # 这里假设session_id从上下文获取
        # 实际实现可能需要从JWT token或请求头中获取
        # 这里简化为从操作记录中查询
        
        if request.operation_id:
            # 回滚单个操作
            success = safety.rollback_operation(request.operation_id)
            
            # 获取操作信息用于响应
            operations = []
            if success:
                operations.append({
                    "operation_id": request.operation_id,
                    "success": True
                })
            
            return RollbackResponse(
                success=success,
                session_id="unknown",  # 实际应从操作记录查询
                total_operations=1,
                success_count=1 if success else 0,
                failed_count=0 if success else 1,
                operations=operations
            )
        else:
            # 回滚整个会话需要session_id
            raise HTTPException(
                status_code=400,
                detail="Session ID required for full session rollback"
            )
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/operations/session/{session_id}/rollback", response_model=RollbackResponse)
async def rollback_session(session_id: str):
    """
    回滚整个会话
    
    - **session_id**: 会话ID
    
    按逆序回滚会话中的所有操作
    """
    try:
        safety = get_file_safety_service()
        result = safety.rollback_session(session_id)
        
        return RollbackResponse(
            success=result["success"] > 0,
            session_id=session_id,
            total_operations=result["total"],
            success_count=result["success"],
            failed_count=result["failed"],
            operations=result["operations"]
        )
        
    except Exception as e:
        logger.error(f"Session rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
