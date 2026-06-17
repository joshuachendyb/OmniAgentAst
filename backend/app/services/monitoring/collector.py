"""
指标收集器模块
负责指标类型定义、指标数据结构和收集逻辑
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from app.utils.logger import logger


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"    # 计数器,只增不减
    GAUGE = "gauge"        # 仪表,可增可减
    HISTOGRAM = "histogram"  # 直方图,统计分布
    SUMMARY = "summary"    # 摘要,分位数计算


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
            retention_period: 指标保留时间(秒),默认1小时
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
    
    def _get_metric_type(self, name: str) -> Optional[Any]:
        """获取指标类型 - 小沈 2026-06-08"""
        metric_type = self._metrics_config.get(name)
        if not metric_type:
            logger.warning(f"未注册的指标名称: {name}")
        return metric_type
    
    def _create_metric(self, name: str, metric_type, value: float, labels: Optional[Dict[str, str]]) -> Metric:
        """创建指标对象 - 小沈 2026-06-08"""
        return Metric(name=name, type=metric_type, value=value, labels=labels)
    
    def _add_metric(self, name: str, metric: Metric) -> None:
        """添加指标到列表 - 小沈 2026-06-08"""
        self.metrics[name].append(metric)
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        记录指标
        
        Args:
            name: 指标名称
            value: 指标值
            labels: 标签字典
        """
        metric_type = self._get_metric_type(name)
        if not metric_type:
            return
        
        metric = self._create_metric(name, metric_type, value, labels)
        self._add_metric(name, metric)
        
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
            
            # 如果列表为空,删除该键
            if not self.metrics[name]:
                del self.metrics[name]
    
    def get_metrics(self, name: Optional[str] = None) -> Dict[str, List[Metric]]:
        """
        获取指标数据
        
        Args:
            name: 指标名称,如果为None则返回所有指标
        
        Returns:
            指标数据字典
        """
        if name:
            return {name: self.metrics.get(name, [])}
        return dict(self.metrics)
    
    def _calculate_basic_stats(self, values: List[float], metrics_list: List[Metric]) -> dict:
        """计算基础统计 - 小沈 2026-06-08"""
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": metrics_list[-1].value,
            "timestamp": metrics_list[-1].timestamp.isoformat(),
        }
    
    def _calculate_percentiles(self, values: List[float]) -> dict:
        """计算分位数 - 小沈 2026-06-08"""
        sorted_values = sorted(values)
        return {
            "p50": sorted_values[int(len(sorted_values) * 0.5)],
            "p90": sorted_values[int(len(sorted_values) * 0.9)],
            "p95": sorted_values[int(len(sorted_values) * 0.95)],
            "p99": sorted_values[int(len(sorted_values) * 0.99)],
        }
    
    def get_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        获取指标摘要
        
        Returns:
            指标摘要字典,包含计数、总和、平均值等
        """
        summary = {}
        
        for name, metrics_list in self.metrics.items():
            if not metrics_list:
                continue
            
            values = [metric.value for metric in metrics_list]
            summary[name] = self._calculate_basic_stats(values, metrics_list)
            
            if metrics_list[0].type == MetricType.HISTOGRAM:
                summary[name].update(self._calculate_percentiles(values))
        
        return summary
    
    def reset(self):
        """重置所有指标"""
        self.metrics.clear()
        self.register_default_metrics()
