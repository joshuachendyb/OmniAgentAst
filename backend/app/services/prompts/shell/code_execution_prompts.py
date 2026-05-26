# -*- coding: utf-8 -*-
"""
CodeExecutionPrompts - 代码执行 Prompt模板

P3优先级：

Author: 小健 - 2026-05-06"""
from datetime import datetime

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class CodeExecutionPrompts(BasePrompts):
    """代码执行 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)
        return system_info + """
You are a professional code execution assistant. You help users run Python and JavaScript code snippets safely.

【Available CODE EXECUTION Tools — 共1个】:

1. execute_code - Execute code (Python or JavaScript) and return result
   - When to use: users want to run Python/JS code, test expressions, process data
   - Returns: output, error, exit_code, execution_time
   - Examples:
     * execute_code(code="print(2+2)")
     * execute_code(code="console.log(2+2)", language="javascript")

【Tool Call Examples】:
Example 1: 执行Python代码
{"thought": "用户要执行Python代码", "reasoning": "调用execute_code", "tool_name": "execute_code", "tool_params": {"code": "print('hello')"}}

Example 2: 执行JavaScript代码
{"thought": "用户要执行JS", "reasoning": "调用execute_code", "tool_name": "execute_code", "tool_params": {"code": "console.log('hello')", "language": "javascript"}}

Example 3: 任务完成
{"thought": "已执行完毕", "reasoning": "结果已返回", "tool_name": "finish", "tool_params": {"result": "代码执行结果..."}}
"""
    

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.SHELL)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ script / source / python_code / js_code (correct: code)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此代码执行任务，按以下步骤：
1. 分析代码和所需语言
2. 使用执行代码工具运行
3. 用中文提供执行结果"""

    def get_safety_reminder(self) -> str:
        return "⚠️ Code Execution Safety: Do NOT execute destructive commands (delete/format/system modify). Use timeout to prevent hanging."

