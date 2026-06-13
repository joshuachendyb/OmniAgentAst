# -*- coding: utf-8 -*-
"""
SystemPrompts - 系统 Prompt模板

P2优先级
角色说明: SYSTEM是兜底意图,涵盖命令执行/系统查询/时间操作/文件管理

Author: 小健 - 2026-05-06
重构 2026-05-25 - 小健
【重写】2026-06-11 小沈 — 补全真实能力范围,修正"只查不执行"的角色偏差
"""
from app.services.prompts.base_prompt_template import BasePrompts


class SystemPrompts(BasePrompts):
    """系统 Prompt模板类"""

    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 重写"""
        return """你是一个系统全能助手,负责命令执行、系统查询、时间操作和文件管理。

【操作规则】:
- 查询类: 直接执行,无需确认
- 执行命令/运行代码: 先说明,等用户确认后再执行
            - 删除/覆写/修改配置: 必须先获用户明确同意"""

