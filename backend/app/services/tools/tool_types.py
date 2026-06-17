# -*- coding: utf-8 -*-
"""
工具类型定义 — 单一定义源(OCP:新增分类只需在此文件添加)
- ToolCategory 枚举
- CATEGORY_ORDER / CATEGORY_NAMES 自动派生

拆分自 registry.py — 小沈 2026-05-29
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ====================================================================
# 一、工具分类枚举
# ====================================================================

class ToolCategory(Enum):
    """
    工具分类枚举

    每个成员携带 (value, order, name_cn):
    - order: 显示排序
    - name_cn: 中文名称
    """
    FILE = ("file", 0, "文件操作工具")
    FUND_RUNTIME = ("fund_runtime", 1, "基础运行时工具")
    NET_PROCESS = ("net_process", 2, "网络与进程工具")
    SCREEN = ("screen", 3, "屏幕交互工具")
    DOC_CONTENT = ("doc_content", 4, "文档内容工具")
    SYSTEM = ("system", 5, "系统管理工具")

    def __new__(cls, value, order, name_cn):
        member = object.__new__(cls)
        member._value_ = value
        member._order = order
        member._name_cn = name_cn
        return member

    @property
    def order(self) -> int:
        return self._order

    @property
    def name_cn(self) -> str:
        return self._name_cn


CATEGORY_ORDER: List[ToolCategory] = sorted(ToolCategory, key=lambda c: c.order)

CATEGORY_NAMES: Dict[ToolCategory, str] = {cat: cat.name_cn for cat in ToolCategory}


# ====================================================================
# （删除Layer 2安全级别枚举 — 2026-06-16 小沈 5级冗余，改用二元安全+check_fn）
# 参见设计文档: doc-6月发展/5级安全系统清理设计方案-20260616.md
# ====================================================================





# ====================================================================
# 二、工具元数据
# ====================================================================

@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    expose_to_llm: bool = True
    next_actions: Dict[str, Any] = field(default_factory=dict)
    failure_hint_fn: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 【2026-06-16 小沈】Layer 2安全字段（替代5级枚举）
    needs_confirmation: bool = False
    action_confirmation: Optional[Dict[str, bool]] = None
    check_fn: Optional[Callable] = None


    def get_failure_hint(self, tool_params: Optional[dict] = None) -> str:
        """获取工具失败时的替代建议 — 小健 2026-05-24"""
        if self.failure_hint_fn:
            try:
                return self.failure_hint_fn(tool_params)
            except Exception as e:
                from app.utils.logger import logger
                logger.warning(f"[ToolMetadata] failure_hint_fn 异常: {e}")
        return ""


__all__ = [
    "ToolCategory",
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "ToolMetadata",
]
