# -*- coding: utf-8 -*-
"""
执行结果模块 - 小健

T3: 执行器增强 - 执行结果类

创建时间: 2026-04-19 10:00:00
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ExecutionResult:
    """
    执行结果
    
    Attributes:
        status: 执行状态 ("success" | "error" | "timeout" | "permission_denied")
        summary: 执行摘要
        data: 返回数据（成功时）
        error: 错误信息（失败时）
        execution_time_ms: 执行时间（毫秒）
        retry_count: 重试次数
        metadata: 元数据（可选）
    """
    status: str
    summary: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为dict"""
        result = {
            "status": self.status,
            "summary": self.summary,
            "execution_time_ms": self.execution_time_ms,
            "retry_count": self.retry_count,
        }
        
        if self.status == "success" and self.data:
            result["data"] = self.data
        elif self.status == "error":
            result["error"] = self.error
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        return result