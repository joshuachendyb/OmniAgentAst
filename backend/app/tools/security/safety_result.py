# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A1 盲点四定案 — SafetyResult dataclass 由 app/safety/tool_safety_checker.py:73 复制迁入
#   (P6 复制原则, 逻辑零改动)。供 tools 层 execute_shell_command_safety 风险检查与 safety 层 tool_safety_checker/delete_safety 共享,
#   消除 tools→safety 越层依赖。
# 2026-08-25 - 小欧 - M1(设计文档 3.2.4): SafetyResult 新增 sandbox_required: bool = False 字段(沙箱预检触发唯一依据);
#   由 tool_safety_checker 在 destructive 级(白名单外授权/路径越权/注册表写等)置位 True, 安全开关总闸在 executor.pre_execute 单点读取, 缺省 False 使存量调用方零感知
"""
safety_result — 安全检查结果数据契约(纯 dataclass)

归属(4.1.7 盲点四, 小欧 2026-08-12): 被 tools 层(Shell 风险检查)与 safety 层(checker)双向消费,
定义在 tools/security 使 tools 层自包含, safety 层依赖 tools 属合法单向。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25
    #15 #50 fix: 删 is_safe 死字段(无人消费) — 小欧 2026-07-18
    # ⑮2026-08-10: 新增 auth_path(白名单外临时授权路径, None=普通确认/无)"""
    blocked: bool = False
    requires_confirmation: bool = False
    message: str = ""
    safety_level: str = "safe"
    auto_confirm: bool = False
    auth_path: Optional[str] = None
    # v1.25 M1: 沙箱预检触发标记 — 由 tool_safety_checker 四条置位路径点亮,
    #   action_handler(M3) 仅对 sandbox_required=True 的工具调用 SandboxExecutor.pre_execute;
    #   缺省 False 不改变既有安全流(非破坏性工具不进沙箱预检, 保性能)
    sandbox_required: bool = False
