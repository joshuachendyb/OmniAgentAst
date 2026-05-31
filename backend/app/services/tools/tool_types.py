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

    每个成员携带元数据：(value, intent_keys, order, name_cn)
    - intent_keys: 可映射到该分类的意图名称列表
    - order: 显示排序
    - name_cn: 中文名称
    INTENT_TO_CATEGORY/CATEGORY_ORDER/CATEGORY_NAMES 从此自动派生。
    新增分类只需添加一个枚举成员 —— 小健 2026-05-31
    """
    FILE = ("file", ["file"], 0, "文件操作工具")
    SYSTEM = ("system", ["shell", "system", "time", "meta", "env", "environment", "code_execution"], 1, "系统/Shell/时间/环境工具")
    NETWORK = ("network", ["network"], 2, "网络通信工具")
    DESKTOP = ("desktop", ["desktop"], 3, "桌面工具")
    DOCUMENT = ("document", ["document", "database", "data_analysis"], 4, "文档(含数据分析与数据库)工具")

    def __new__(cls, value, intent_keys, order, name_cn):
        member = object.__new__(cls)
        member._value_ = value
        member._intent_keys = intent_keys
        member._order = order
        member._name_cn = name_cn
        return member

    @property
    def intent_keys(self) -> List[str]:
        return self._intent_keys

    @property
    def order(self) -> int:
        return self._order

    @property
    def name_cn(self) -> str:
        return self._name_cn


INTENT_TO_CATEGORY: Dict[str, ToolCategory] = {
    k: cat for cat in ToolCategory for k in cat.intent_keys
}

CATEGORY_ORDER: List[ToolCategory] = sorted(ToolCategory, key=lambda c: c.order)

CATEGORY_NAMES: Dict[ToolCategory, str] = {cat: cat.name_cn for cat in ToolCategory}


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
