"""
监控中间件模块
负责HTTP请求监控和门面函数
"""

import time
from typing import Dict, List, Optional, Any

from app.utils.logger import logger
from app.utils.monitoring.collector import MetricsCollector, Metric


# 全局指标收集器实例
_collector = MetricsCollector()


class MonitoringMiddleware:
    """监控中间件"""
    
    def __init__(self, app, collector: MetricsCollector = _collector):
        self.app = app
        self.collector = collector
    
    def _extract_request_info(self, scope) -> dict:
        """提取请求信息 - 小沈 2026-06-08"""
        return {
            "path": scope.get("path", ""),
            "method": scope.get("method", "GET"),
            "start_time": time.time(),
            "request_size": 0,
        }
    
    def _record_error(self, error: Exception, request_info: dict) -> None:
        """记录错误指标 - 小沈 2026-06-08"""
        self.collector.record_metric(
            name="errors_total",
            value=1,
            labels={
                "method": request_info["method"],
                "path": request_info["path"],
                "error": type(error).__name__
            }
        )
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request_info = self._extract_request_info(scope)
        wrapped_send = self._make_send_wrapper(
            send,
            request_info["start_time"],
            request_info["method"],
            request_info["path"],
            request_info["request_size"]
        )
        
        try:
            await self.app(scope, receive, wrapped_send)
        except Exception as e:
            self._record_error(e, request_info)
            raise
    
    def _make_send_wrapper(self, send, start_time, method, path, request_size):
        """创建包装send — 闭包提取为工厂方法 — 小健 2026-05-29"""
        async def wrapper(message):
            if message["type"] == "http.response.start":
                self._record_response_metrics(message, start_time, method, path, request_size)
            await send(message)
        return wrapper
    
    def _record(self, name: str, value: float, labels: dict) -> None:
        """记录单个指标 - 小沈 2026-06-08"""
        self.collector.record_metric(name=name, value=value, labels=labels)
    
    def _record_response_metrics(self, message, start_time, method, path, request_size):
        """记录响应指标 — 提取的独立方法 — 小健 2026-05-29"""
        status_code = message["status"]
        base_labels = {"method": method, "path": path}
        
        self._record("http_requests_total", 1, {**base_labels, "status": str(status_code)})
        
        duration = time.time() - start_time
        self._record("http_request_duration_seconds", duration, base_labels)
        
        self._record("http_request_size_bytes", request_size, base_labels)
        
        if status_code >= 400:
            self._record("errors_total", 1, {**base_labels, "status": str(status_code)})


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
        name: 指标名称,如果为None则返回所有指标
    
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
