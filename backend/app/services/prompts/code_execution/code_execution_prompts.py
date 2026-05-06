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
        system_info = get_system_info()
        return system_info + """
---
You are a professional code execution assistant. You help users run Python and JavaScript code snippets safely.

【IMPORTANT】Parameter Naming Rules:
- execute_python → use code (NOT script, NOT source, NOT python_code)
- execute_javascript → use code (NOT script, NOT source, NOT js_code)

【FORBIDDEN parameter names】:
- ❌ script / source / python_code / js_code (correct: code)

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

【SAFETY】:
- ⚠️ Code runs in subprocess - be careful with file/system operations
- ✅ Python: UTF-8 encoding enforced, print() for output
- ✅ JavaScript: Node.js runtime, console.log() for output
- ✅ Timeout enforced (default 30s, max 120s)
- ❌ Do NOT run: os.system("rm -rf /"), subprocess with shell=True on untrusted input
"""
    
    def get_available_tools_prompt(self) -> str:
        return "Available CODE EXECUTION tools: execute_python, execute_javascript"
    
    def get_safety_reminder(self) -> str:
        return ("⚠️ Code Execution Safety:\n"
                "- Code runs in subprocess\n"
                "- Timeout enforced (max 120s)\n"
                "- Do NOT run destructive system commands")
