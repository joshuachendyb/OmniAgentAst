"""
监控指标API路由
提供运行时指标和性能监控数据
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.utils.monitoring import get_metrics_summary, get_raw_metrics, reset_metrics
from app.utils.logger import logger

router = APIRouter()

class MetricSummary(BaseModel):
    """指标摘要"""
    count: float = Field(..., description="指标数量")
    sum: float = Field(..., description="指标总和")
    min: float = Field(..., description="最小值")
    max: float = Field(..., description="最大值")
    avg: float = Field(..., description="平均值")
    latest: float = Field(..., description="最新值")
    timestamp: str = Field(..., description="时间戳")
    p50: Optional[float] = Field(None, description="50分位数（仅直方图）")
    p90: Optional[float] = Field(None, description="90分位数（仅直方图）")
    p95: Optional[float] = Field(None, description="95分位数（仅直方图）")
    p99: Optional[float] = Field(None, description="99分位数（仅直方图）")

class MetricsResponse(BaseModel):
    """指标响应"""
    success: bool = Field(..., description="是否成功")
    metrics: Dict[str, MetricSummary] = Field(..., description="指标摘要")
    timestamp: str = Field(..., description="响应时间戳")
    total_metrics: int = Field(..., description="总指标数量")

class ResetMetricsRequest(BaseModel):
    """重置指标请求"""
    confirm: bool = Field(..., description="确认重置，必须为True")

class ResetMetricsResponse(BaseModel):
    """重置指标响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="重置结果消息")
    timestamp: str = Field(..., description="重置时间戳")

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    获取监控指标摘要
    
    返回当前运行时的性能指标，包括：
    - HTTP请求总数、持续时间、大小
    - 错误总数
    - 请求进行中的数量
    """
    try:
        summary = get_metrics_summary()
        total_metrics = sum(len(metrics) for metrics in get_raw_metrics().values())
        
        # 转换字典为MetricSummary对象
        metrics_dict = {
            name: MetricSummary(**data) 
            for name, data in summary.items()
        }
        
        return MetricsResponse(
            success=True,
            metrics=metrics_dict,
            timestamp=datetime.utcnow().isoformat(),
            total_metrics=total_metrics
        )
    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取监控指标失败: {str(e)}"
        )

@router.get("/metrics/raw")
async def get_raw_metrics_endpoint(name: Optional[str] = None):
    """
    获取原始指标数据
    
    Args:
        name: 指标名称，如果不提供则返回所有指标
        
    返回原始指标数据，包含每个数据点的时间戳和标签
    """
    try:
        raw_metrics = get_raw_metrics(name)
        return {
            "success": True,
            "metrics": raw_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"获取原始指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取原始指标失败: {str(e)}"
        )

@router.post("/metrics/reset", response_model=ResetMetricsResponse)
async def reset_metrics_endpoint(request: ResetMetricsRequest):
    """
    重置所有监控指标
    
    需要确认参数confirm=true
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="必须设置confirm=true来确认重置指标"
        )
    
    try:
        reset_metrics()
        return ResetMetricsResponse(
            success=True,
            message="所有监控指标已重置",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"重置指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"重置监控指标失败: {str(e)}"
        )

@router.get("/metrics/health")
async def metrics_health_check():
    """
    监控系统健康检查
    
    检查监控系统是否正常工作
    """
    try:
        # 尝试获取指标摘要来验证系统是否正常工作
        get_metrics_summary()
        return {
            "success": True,
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "监控系统运行正常"
        }
    except Exception as e:
        return {
            "success": False,
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"监控系统异常: {str(e)}"
        }