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

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


def _build_category_header(name: str, count: int, desc: str = "") -> str:
    """统一构建分类标题 - 小健 2026-05-25

    使用场景:
    - get_system_prompt中构建分类标题

    使用示例:
        header = _build_category_header(name, count, desc)

    返回数据说明:
    - 返回str，分类标题行
    """
    return f"# {name} 工具 ({count}个){' - ' + desc if desc else ''}\n"


def _build_tool_descriptions(category: str, tool_names: List[str]) -> str:
    """从工具名称列表构建分类工具描述 — 委托到 BasePrompts.build_tool_descriptions — 小沈 2026-05-27"""
    from app.services.prompts.BasePromptTemplate import BasePrompts

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
        {"thought": "用户想了解天气", "reasoning": "需要使用天气工具", "tool_name": "get_weather", "tool_params": {"city": "北京"}},
        {"thought": "用户问了一个简单问题", "reasoning": "直接回答即可", "tool_name": "finish", "tool_params": {"result": "答案"}},
        {"thought": "需要搜索文件", "reasoning": "使用 search_files 工具", "tool_name": "search_files", "tool_params": {"pattern": "*.py", "search_dir": "/home"}},
        {"thought": "需要读取文件内容", "reasoning": "使用 read_file 工具", "tool_name": "read_file", "tool_params": {"file_path": "/path/to/file"}},
        {"thought": "执行命令", "reasoning": "调用execute_shell_command", "tool_name": "execute_shell_command", "tool_params": {"command": "dir"}},
        {"thought": "任务完成", "reasoning": "结果已返回，无更多操作", "tool_name": "finish", "tool_params": {"result": "任务完成"}},
    ]

    lines = ["  以下是一些 ReAct 调用示例："]
    for i, ex in enumerate(_EXAMPLE_TEMPLATES[:count], 1):
        lines.append(f"  示例{i}：{json.dumps(ex, ensure_ascii=False, indent=6)}")
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
            (ToolCategory.SYSTEM, "系统信息/文件操作"),
            (ToolCategory.SHELL, "命令执行"),
            (ToolCategory.META, "时间/工具/管道")
        ]

        parts = [system_info]
        for category, desc in categories:
            tool_names = tool_registry.get_categories().get(category, [])
            parts.append(_build_category_header(category.value, len(tool_names), desc))
            parts.append(_build_tool_descriptions(category.value, tool_names))
        parts.append(_build_examples(6))

        return "\n".join(parts)

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry
        from app.services.tools.tool_types import ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.SYSTEM)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ cmd (correct: command)\n"
            "- ❌ dir (correct: working_directory)\n"
            "- ❌ cwd (correct: working_directory)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此系统信息任务，按以下步骤：
1. 分析需要什么系统信息
2. 使用合适的系统工具
3. 用中文总结系统信息"""

    def get_safety_reminder(self) -> str:
        return "⚠️ System Safety: Registry write/delete operations are destructive and irreversible. Confirm before execution."
