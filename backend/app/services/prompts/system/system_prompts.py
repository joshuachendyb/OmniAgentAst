# -*- coding: utf-8 -*-
"""
SystemPrompts - 系统信息 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
重构 2026-05-25 - 小健
"""
import json
from datetime import datetime
from typing import Dict, List

from app.services.prompts.base_prompt_template import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


def _build_tool_descriptions(category: str, tool_names: List[str]) -> str:
    """从工具名称列表构建分类工具描述 — 委托到 BasePrompts.build_tool_descriptions — 小沈 2026-05-27"""
    from app.services.prompts.base_prompt_template import BasePrompts

    CATEGORY_NAME_MAP = {
        "SYSTEM": "SYSTEM",
        "SHELL": "SHELL",
        "NETWORK": "NETWORK",
        "DESKTOP": "DESKTOP",
        "DOCUMENT": "DOCUMENT",
        "META": "META",
    }

    from app.services.tools.tool_types import ToolCategory
    mapped_category = CATEGORY_NAME_MAP.get(str(category), str(category))
    return BasePrompts.build_tool_descriptions(tool_names, category_label=mapped_category)


def _build_examples(count: int = 4) -> str:
    """从模板池选取 N 个生成 JSON 示例 - 小健 2026-05-25

    使用场景:
    - get_system_prompt中生成示例

    使用示例:
        examples = _build_examples(6)

    返回数据说明:
    - 返回str, 示例块
    """
    _EXAMPLE_TEMPLATES = [
        {"thought": "分析:用户需要询问当前时间", "reasoning": "用户直接询问时间,调用时间工具即可", "tool_name": "get_time", "tool_params": {"action": "now"}},
        {"thought": "分析:用户询问今天是否工作日", "reasoning": "需要查询日历确认日期属性", "tool_name": "query_calendar", "tool_params": {"date": "2026-06-11", "check_type": "workday"}},
        {"thought": "分析:用户想查看系统配置", "reasoning": "需要获取系统信息", "tool_name": "get_system_info", "tool_params": {"info_type": "os"}},
        {"thought": "分析:用户需要查看进程状态", "reasoning": "列出进程列表", "tool_name": "list_processes", "tool_params": {"filter": "python"}},
        {"thought": "分析:用户问题可直接回答", "reasoning": "直接回答", "tool_name": "finish", "tool_params": {"result": "答案"}},
        {"thought": "分析:任务已完成", "reasoning": "结果已返回,无更多操作", "tool_name": "finish", "tool_params": {"result": "任务完成"}},
    ]

    lines = ["  以下是一些 ReAct 调用示例:"]
    for i, ex in enumerate(_EXAMPLE_TEMPLATES[:count], 1):
        lines.append(f"  示例{i}:{json.dumps(ex, ensure_ascii=False)}")
    return "\n".join(lines)


class SystemPrompts(BasePrompts):
    """系统信息 Prompt模板类"""

    def get_system_prompt(self) -> str:
        """获取系统提示词 - 小健 2026-05-25 重构

        返回:
            str: 系统提示词字符串
        """
        system_info = get_system_prompt_string(include_commands=False)
        from app.services.tools.registry import tool_registry
        from app.services.tools.tool_types import ToolCategory

        categories = [
            (ToolCategory.FUND_RUNTIME, "基础运行时(命令/时间/工具/系统信息)"),
        ]

        parts = [system_info]
        for category, desc in categories:
            tool_names = tool_registry.get_categories().get(category, [])
            header = f"# {category.value} 工具 ({len(tool_names)}个){' - ' + desc if desc else ''}\n"
            parts.append(header)
            parts.append(_build_tool_descriptions(category.value, tool_names))
        parts.append(_build_examples(6))

        return "\n".join(parts)

    def _get_domain_name(self) -> str:
        return "系统信息"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要什么系统信息\n2. 使用合适的系统工具\n3. 用中文总结系统信息"

    def get_safety_reminder(self) -> str:
        return "⚠️ System Safety: Registry write/delete operations are destructive and irreversible. Confirm before execution."
