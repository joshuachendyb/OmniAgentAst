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
# 四、工具安全级别（Layer 2）— 小沈 2026-06-09
# ====================================================================

class ToolSafetyLevel(Enum):
    """
    工具安全级别五级分级
    
    v3.4修复：区分沙箱内危险和系统级危险
    """
    READ_ONLY = "read_only"              # 纯读取，无副作用
    SAFE = "safe"                        # 有副作用但可逆或无害
    DESTRUCTIVE = "destructive"          # 破坏性操作，不可逆
    DANGEROUS_SANDBOX = "dangerous_sandbox"  # 沙箱内危险(execute_python/execute_js)
    DANGEROUS = "dangerous"              # 系统级危险(execute_shell_command/kill_process)


# SAFETY_POLICY默认值（配置驱动，支持运行时调整）
DEFAULT_SAFETY_POLICY = {
    ToolSafetyLevel.READ_ONLY:          {"needs_confirmation": False, "needs_safety_check": False},
    ToolSafetyLevel.SAFE:               {"needs_confirmation": False, "needs_safety_check": False},
    ToolSafetyLevel.DESTRUCTIVE:        {"needs_confirmation": True,  "needs_safety_check": True},
    ToolSafetyLevel.DANGEROUS_SANDBOX:  {"needs_confirmation": True,  "needs_safety_check": True},
    ToolSafetyLevel.DANGEROUS:          {"needs_confirmation": True,  "needs_safety_check": True},
}





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
    
    # 【v3.4新增】Layer 2安全级别字段 — 小沈 2026-06-09
    safety_level: ToolSafetyLevel = ToolSafetyLevel.SAFE
    action_safety_map: Optional[Dict[str, ToolSafetyLevel]] = None
    # 【借鉴OpenCode】工具使用注意事项 — 小沈 2026-06-11
    critical_notes: str = ""      # 关键注意事项（LLM必须知道的风险/限制）
    usage_hint: str = ""          # 使用提示（最佳实践）
    forbidden: str = ""           # 禁止用法（什么情况下不能使用此工具）

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
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "ToolMetadata",
    "ToolSafetyLevel",
    "DEFAULT_SAFETY_POLICY",
]
