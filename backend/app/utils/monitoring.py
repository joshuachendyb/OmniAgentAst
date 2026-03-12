"""
监控和指标收集模块
用于收集运行时指标和性能监控
"""

import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum

from app.utils.logger import logger

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"    # 计数器，只增不减
    GAUGE = "gauge"        # 仪表，可增可减
    HISTOGRAM = "histogram"  # 直方图，统计分布
    SUMMARY = "summary"    # 摘要，分位数计算


@dataclass
class Metric:
    """基础指标类"""
    name: str
    type: MetricType
    value: float
    labels: Optional[Dict[str, str]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, retention_period: int = 3600):
        """
        初始化指标收集器
        
        Args:
            retention_period: 指标保留时间（秒），默认1小时
        """
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.retention_period = retention_period
        # 注册内置指标
        self.register_default_metrics()
        
    def register_default_metrics(self):
        """注册默认指标"""
        self._metrics_config = {
            "http_requests_total": MetricType.COUNTER,
            "http_request_duration_seconds": MetricType.HISTOGRAM,
            "http_request_size_bytes": MetricType.HISTOGRAM,
            "http_response_size_bytes": MetricType.HISTOGRAM,
            "http_requests_in_progress": MetricType.GAUGE,
            "errors_total": MetricType.COUNTER,
        }
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        记录指标
        
        Args:
            name: 指标名称
            value: 指标值
            labels: 标签字典
        """
        metric_type = self._metrics_config.get(name)
        if not metric_type:
            logger.warning(f"未注册的指标名称: {name}")
            return
        
        metric = Metric(name=name, type=metric_type, value=value, labels=labels)
        self.metrics[name].append(metric)
        
        # 清理过期指标
        self._cleanup_old_metrics()
    
    def _cleanup_old_metrics(self):
        """清理过期的指标"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.retention_period)
        
        for name, metrics_list in list(self.metrics.items()):
            # 保留最近期的指标
            self.metrics[name] = [
                metric for metric in metrics_list 
                if metric.timestamp > cutoff_time
            ]
            
            # 如果列表为空，删除该键
            if not self.metrics[name]:
                del self.metrics[name]
    
    def get_metrics(self, name: Optional[str] = None) -> Dict[str, List[Metric]]:
        """
        获取指标数据
        
        Args:
            name: 指标名称，如果为None则返回所有指标
        
        Returns:
            指标数据字典
        """
        if name:
            return {name: self.metrics.get(name, [])}
        return dict(self.metrics)
    
    def get_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        获取指标摘要
        
        Returns:
            指标摘要字典，包含计数、总和、平均值等
        """
        summary = {}
        
        for name, metrics_list in self.metrics.items():
            if not metrics_list:
                continue
                
            values = [metric.value for metric in metrics_list]
            summary[name] = {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "latest": metrics_list[-1].value,
                "timestamp": metrics_list[-1].timestamp.isoformat(),
            }
            
            # 如果是直方图类型，添加分位数计算
            if metrics_list[0].type == MetricType.HISTOGRAM:
                sorted_values = sorted(values)
                summary[name]["p50"] = sorted_values[int(len(sorted_values) * 0.5)]
                summary[name]["p90"] = sorted_values[int(len(sorted_values) * 0.9)]
                summary[name]["p95"] = sorted_values[int(len(sorted_values) * 0.95)]
                summary[name]["p99"] = sorted_values[int(len(sorted_values) * 0.99)]
        
        return summary
    
    def reset(self):
        """重置所有指标"""
        self.metrics.clear()
        self.register_default_metrics()


# 全局指标收集器实例
_collector = MetricsCollector()


class MonitoringMiddleware:
    """监控中间件"""
    
    def __init__(self, app, collector: MetricsCollector = _collector):
        self.app = app
        self.collector = collector
    
    async def __call__(self, scope, receive, send):
        # 只处理HTTP请求
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        # 提取请求信息
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        
        # 记录请求开始
        start_time = time.time()
        request_size = 0
        
        # 创建一个发送包装器来捕获响应信息
        async def send_wrapper(message):
            nonlocal start_time
            
            if message["type"] == "http.response.start":
                status_code = message["status"]
                
                # 记录请求指标
                self.collector.record_metric(
                    name="http_requests_total",
                    value=1,
                    labels={"method": method, "path": path, "status": str(status_code)}
                )
                
                # 记录请求持续时间
                duration = time.time() - start_time
                self.collector.record_metric(
                    name="http_request_duration_seconds",
                    value=duration,
                    labels={"method": method, "path": path}
                )
                
                # 记录请求大小（估算）
                self.collector.record_metric(
                    name="http_request_size_bytes",
                    value=request_size,
                    labels={"method": method, "path": path}
                )
                
                # 如果是错误状态码，记录错误
                if status_code >= 400:
                    self.collector.record_metric(
                        name="errors_total",
                        value=1,
                        labels={"method": method, "path": path, "status": str(status_code)}
                    )
            
            await send(message)
        
        # 处理请求
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # 记录未捕获的异常
            self.collector.record_metric(
                name="errors_total",
                value=1,
                labels={"method": method, "path": path, "error": type(e).__name__}
            )
            raise


def setup_monitoring(app) -> MetricsCollector:
    """
    设置监控中间件
    
    Args:
        app: FastAPI应用实例
    
    Returns:
        指标收集器实例
    """
    # 添加监控中间件
    app.add_middleware(MonitoringMiddleware)
    
    logger.info("监控中间件已启用")
    return _collector


def record_request(method: str, path: str, status_code: int, duration: float, 
                  request_size: int = 0, response_size: int = 0):
    """
    记录HTTP请求指标（供外部调用）
    
    Args:
        method: HTTP方法
        path: 请求路径
        status_code: 状态码
        duration: 请求持续时间（秒）
        request_size: 请求大小（字节）
        response_size: 响应大小（字节）
    """
    _collector.record_metric(
        name="http_requests_total",
        value=1,
        labels={"method": method, "path": path, "status": str(status_code)}
    )
    
    _collector.record_metric(
        name="http_request_duration_seconds",
        value=duration,
        labels={"method": method, "path": path}
    )
    
    if request_size > 0:
        _collector.record_metric(
            name="http_request_size_bytes",
            value=request_size,
            labels={"method": method, "path": path}
        )
    
    if response_size > 0:
        _collector.record_metric(
            name="http_response_size_bytes",
            value=response_size,
            labels={"method": method, "path": path}
        )
    
    if status_code >= 400:
        _collector.record_metric(
            name="errors_total",
            value=1,
            labels={"method": method, "path": path, "status": str(status_code)}
        )


def record_error(error_type: str, message: str = "", labels: Optional[Dict[str, str]] = None):
    """
    记录错误指标
    
    Args:
        error_type: 错误类型
        message: 错误消息
        labels: 附加标签
    """
    if labels is None:
        labels = {}
    
    labels["error_type"] = error_type
    if message:
        labels["message"] = message
    
    _collector.record_metric(
        name="errors_total",
        value=1,
        labels=labels
    )


def get_metrics_summary() -> Dict[str, Dict[str, Any]]:
    """
    获取指标摘要
    
    Returns:
        指标摘要字典
    """
    return _collector.get_summary()


def get_raw_metrics(name: Optional[str] = None) -> Dict[str, List[Metric]]:
    """
    获取原始指标数据
    
    Args:
        name: 指标名称，如果为None则返回所有指标
    
    Returns:
        原始指标数据
    """
    return _collector.get_metrics(name)


def reset_metrics():
    """
    重置所有指标
    """
    _collector.reset()
    logger.info("所有指标已重置")


# 导出公共接口
__all__ = [
    "setup_monitoring",
    "record_request",
    "record_error",
    "get_metrics_summary",
    "get_raw_metrics",
    "reset_metrics",
]