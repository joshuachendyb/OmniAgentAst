"""
监控和指标收集模块

【10大原则规范 2026-05-30 小健】
- SRP: monitoring.py facade已删除,实现拆分到collector / middleware子模块
- KISS: 本文件仅做导出入口,不混入实现逻辑
- 禁止向后兼容: monitoring.py旧入口已删除,统一从 monitoring/ 包导入
小欧 2026-08-14 monitoring 独立为 app 顶层能力层目录(services/monitoring→app/monitoring), 包内 import 路径同步
"""

from app.monitoring.collector import MetricType, Metric, MetricsCollector
from app.monitoring.middleware import (
    MonitoringMiddleware,
    setup_monitoring,
    get_metrics_summary,
    get_raw_metrics,
    reset_metrics,
)

__all__ = [
    "setup_monitoring",
    "get_metrics_summary",
    "get_raw_metrics",
    "reset_metrics",
]
