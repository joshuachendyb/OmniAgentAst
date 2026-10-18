# -*- coding: utf-8 -*-
"""safety_result — 安全检查结果契约(安全层单一定义源) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: SafetyResult 契约回迁系统层, 自 app/tools/tool_types.py 迁入。
  生产者(delete/write/read_path_check、shell_command_risk、shell_danger_command、
  path_legality_router、path_tool_safety_checker、dual_path_check、shell_path_check)全部在
  app/safety/ 内; 消费者在 app/services/(safety_gate/hitl_gateway/tool_facade)与工具层
  只读字段(execute_shell_command 只读 blocked/needs_confirm, 不 import 本类)。
  契约随生产者走, 落在安全层即免去用工具层模块迁就安全语义。禁 backward 双份契约。

分层: 本文件只持契约(纯 dataclass, 无任何逻辑), 不做任何判定。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25

    字段全部为安全裁决语义, 由各判定分支直接构造(kwarg), 丢一个字段即 TypeError。
    """
    blocked: bool = False
    needs_confirm: bool = False
    message: str = ""
    safety_level: str = ""          # 问题来源分类: path_auth / shellparam / command_block /
                                     #   tool_delete / tool_write / data_guard / unregistered /
                                     #   forbidden_zone / tool_execute
    auto_confirm: bool = False
    auth_path: Optional[str] = None
    sandbox_required: bool = False  # 沙箱预检触发标记: 由 path_tool_safety_checker 四条置位路径点亮,
                                     #   action_handler 仅对 True 者调 SandboxExecutor.pre_execute;
                                     #   缺省 False 不改变既有安全流(非破坏性工具不进沙箱预检)

    @staticmethod
    def pass_result() -> "SafetyResult":
        """放行结果工厂(每次新建实例, 防共享单例被下游改写) — 小欧 2026-10-17(三线/通道统一放行)

        供 path_legality_router / dual_path_check / shell_path_check 复用, 免三份拷贝与循环导入。
        """
        return SafetyResult(blocked=False, needs_confirm=False, message="")


__all__ = ["SafetyResult"]
