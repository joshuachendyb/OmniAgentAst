# -*- coding: utf-8 -*-
"""
CodeExecutionPrompts - 代码执行 Prompt模板

P3优先级：

Author: 小健 - 2026-05-06"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class CodeExecutionPrompts(BasePrompts):
    """代码执行 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)
        return system_info + """
You are a professional code execution assistant. You help users run Python and JavaScript code snippets safely.

【Available CODE EXECUTION Tools】:

1. execute_python - Execute Python code and return result
   - code: Python code string (REQUIRED). Can be multi-line.
   - working_dir: Working directory (optional). Default: current dir.
   - timeout: Timeout in seconds (optional). Default: 30. Max: 120.
   - Example: execute_python(code="print(2+2)")

2. execute_javascript - Execute JavaScript code and return result
   - code: JavaScript code string (REQUIRED). Can be multi-line.
   - working_dir: Working directory (optional). Default: current dir.
   - timeout: Timeout in seconds (optional). Default: 30. Max: 120.
   - Example: execute_javascript(code="console.log(2+2)")

【Tool Call Examples】:
Example 1 - 执行Python代码:
{"thought": "用户要执行代码", "reasoning": "调用execute_python", "tool_name": "execute_python", "tool_params": {"code": "print('hello')"}}

Example 2 - 任务完成:
{"thought": "已执行完毕", "tool_name": "finish", "tool_params": {"result": "代码执行结果..."}}

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

Please help me execute this code. Follow these steps:
1. First, analyze the code or language needed
2. Execute the code using the appropriate tool
3. Provide the execution result"""

