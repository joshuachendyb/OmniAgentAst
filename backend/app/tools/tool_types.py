# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 - 小健 - 三堂会审: ToolMetadata 新增 target_param 字段(操作对象/主参数显式声明扩展点), 供 action_handler._resolve_target_field 优先采用; 留空则按schema属性自动推导(DRY/OCP)
# 2026-10-02 - 小欧 - 删 SHELL 枚举(which 归 SYSTEM 后该分类归零; 空分类会写入 searchtool 描述误导 LLM);
#   order 留空位号2不动, 避免 patch_search_desc 排序变化 — 小欧-2026-10-02
# 2026-10-14 - 小欧 - 文档[33] 4.11-D: 承接 SafetyResult dataclass(迁自 app/tools/security/safety_result.py, 该模块随整包删除); 禁 backward 双份契约
# 2026-10-15 - 小欧 - 文档[35] 跟随: action_kind 注释"multi"去 edit(单路径改走写线)、删"none"档(通道 A 零命中即放行); 表名 TOOL_ACTION_KINDS→PATH_ACTION_KINDS。
"""
工具类型定义 — 单一定义源(OCP:新增分类只需在此文件添加)
- ToolCategory 枚举
- CATEGORY_ORDER / CATEGORY_NAMES 自动派生

拆分自 registry.py — 小沈 2026-05-29
"""

from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from app.logger import logger


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
    FUNDAMENTAL = ("fundamental", 1, "基础工具")
    # 2026-10-02 小欧 - SHELL 分类已删, order 留空位号2不动(避免 searchtool 排序变化)
    NETWORK = ("network", 3, "网络请求工具")
    DESKTOP = ("desktop", 4, "桌面交互工具")
    DOCUMENT = ("document", 5, "文档操作工具")
    DATAANALYSIS = ("dataanalysis", 6, "数据分析工具")
    SYSTEM = ("system", 7, "系统管理工具")
    TIMER = ("timer", 8, "定时器工具")
    WIN_REGISTRY = ("win_registry", 9, "注册表工具")

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
    input_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    expose_to_llm: bool = True
    failure_hint_fn: Optional[Callable] = None
    
    # 【2026-06-16 小沈】Layer 2安全字段（替代5级枚举）
    needs_confirmation: bool = False
    action_confirmation: Optional[Dict[str, bool]] = None
    check_fn: Optional[Callable] = None
    
    # 【2026-06-18 小健】工具依赖管理
    dependencies: List[Union[str, Dict[str, Any]]] = field(default_factory=list)

    # 【2026-08-18 小健 三堂会审】主参数(操作对象字段名): target展示自动推导的显式声明扩展点;
    # 留空则由action_handler._TARGET_PARAM_PRIORITY按input_schema.properties自动推导(DRY/OCP)
    target_param: Optional[str] = None

    # 【2026-10-15 小欧 — 文档[35] 阶段三】动作类型(读/写/删), 由 tool_constants.PATH_ACTION_KINDS
    # 在注册时按工具名赋值。取代 path_check_entry 原先的运行时 if 链推断。
    #   "read"    只读, 路径检查走 read_path_check(禁区放行, 不弹授权)
    #   "write"   写入或改写, 走 write_path_check
    #   "delete"  删除, 走 delete_path_check(禁区硬拦, 永不授权)
    #   "multi"   一调用内含多个路径动作(copy/move/compress/extract/rename),
    #             走 multi_path_check 按参数分别归线; 单路径的 edit 不得进此档
    # 默认 "write" 是 fail-closed 方向: 未声明的新工具按最严档处理, 与改造前 else 分支行为一致。
    action_kind: str = "write"


    def get_failure_hint(self, tool_params: Optional[dict] = None) -> str:
        """获取工具失败时的替代建议 — 小健 2026-05-24"""
        if self.failure_hint_fn:
            try:
                return self.failure_hint_fn(tool_params)
            except Exception as e:
                logger.warning(f"[ToolMetadata] failure_hint_fn 异常: {e}")
        return ""


__all__ = [
    "ToolCategory",
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "ToolMetadata",
    "SafetyResult",
]


# ====================================================================
# 三、安全检查结果契约（迁自 app/tools/security/safety_result.py）
# ====================================================================
# 2026-10-14 小欧 - 文档[33] 4.11-D: SafetyResult 由 app/tools/security/safety_result.py 迁入。
#   与 ToolCategory/ToolMetadata 同族(工具层数据契约单源); 原模块随 app/tools/security/ 整包删除。
#   禁 backward 双份: 双份 dataclass 会让 isinstance 判定恒 False 且不报错。

@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25
    # 修复: 删 is_safe 死字段(无人消费) — 小欧 2026-07-18
    # ⑮2026-08-10: 新增 auth_path(白名单外临时授权路径, None=普通确认/无)

    逐字复制自 app/tools/security/safety_result.py:20（文档[33] 4.11-D），字段/默认值零改动 ——
    下游均按 kwarg 构造, 丢一个字段即 TypeError。
    """
    blocked: bool = False
    requires_confirmation: bool = False
    message: str = ""
    severity: str = "safe"
    auto_confirm: bool = False
    auth_path: Optional[str] = None
    # v1.25 M1: 沙箱预检触发标记 — 由 tool_safety_checker 四条置位路径点亮,
    #   action_handler(M3) 仅对 sandbox_required=True 的工具调用 SandboxExecutor.pre_execute;
    #   缺省 False 不改变既有安全流(非破坏性工具不进沙箱预检, 保性能)
    sandbox_required: bool = False
