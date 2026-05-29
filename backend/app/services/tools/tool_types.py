# -*- coding: utf-8 -*-
"""
工具类型定义 — 纯数据定义，无业务逻辑，无项目内部依赖

拆分自 registry.py — 小沈 2026-05-29
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ToolCategory(Enum):
    """
    工具分类枚举
    """
    FILE = "file"          # 文件操作
    SYSTEM = "system"      # 系统操作（包含shell、meta、time、environment、code_execution）
    NETWORK = "network"    # 网络通信
    DESKTOP = "desktop"    # 桌面功能
    DOCUMENT = "document"  # 文档读写（包含database、data_analysis）


INTENT_TO_CATEGORY: Dict[str, ToolCategory] = {
    "file": ToolCategory.FILE,
    "shell": ToolCategory.SYSTEM,
    "network": ToolCategory.NETWORK,
    "system": ToolCategory.SYSTEM,
    "desktop": ToolCategory.DESKTOP,
    "document": ToolCategory.DOCUMENT,
}

CATEGORY_ORDER = [
    ToolCategory.FILE, ToolCategory.SYSTEM, ToolCategory.NETWORK,
    ToolCategory.DESKTOP, ToolCategory.DOCUMENT,
]

CATEGORY_NAMES = {
    ToolCategory.FILE: "文件操作工具",
    ToolCategory.SYSTEM: "系统/Shell/时间/环境工具",
    ToolCategory.NETWORK: "网络通信工具",
    ToolCategory.DESKTOP: "桌面工具",
    ToolCategory.DOCUMENT: "文档(含数据分析与数据库)工具",
}


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    expose_to_llm: bool = True
    next_actions: Dict[str, Any] = field(default_factory=dict)
    failure_hint_fn: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.examples is None:
            self.examples = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def get_failure_hint(self, tool_params: Optional[dict] = None) -> str:
        """获取工具失败时的替代建议 — 小健 2026-05-24"""
        if self.failure_hint_fn:
            try:
                return self.failure_hint_fn(tool_params)
            except Exception:
                pass
        return ""


__all__ = [
    "ToolCategory",
    "INTENT_TO_CATEGORY",
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "ToolMetadata",
]
