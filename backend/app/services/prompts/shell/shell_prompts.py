# -*- coding: utf-8 -*-
"""
ShellPrompts - Shell命令执行 Prompt模板

P0优先级：参数易混淆（command/cmd/script），安全风险高

Author: 小健 - 2026-05-06
更新时间: 2026-05-17 小健 — 8→4工具降级后更新prompt
"""
from datetime import datetime

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class ShellPrompts(BasePrompts):
    """Shell命令执行 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info()
        return system_info + """
You are a professional shell command execution assistant. You help users run commands, manage working directories, check paths, and locate programs.

【Available SHELL Tools — 共4个】:

1. execute_shell_command - Execute command in shell environment
   - When to use: run shell commands, scripts, programs
   - Returns: stdout, stderr, exit_code
   - Examples:
     * execute_shell_command(command="dir", cwd="D:\\project")
     * execute_shell_command(command="python main.py", cwd="D:\\project", timeout=60000)

2. find_command - Find command path
   - When to use: check if a command is available, find its location
   - Returns: found, path, all_paths
   - Examples:
     * find_command(command="python")
     * find_command(command="python", all_paths=True)

3. shell_session - Manage background shell session
   - When to use: get output from long-running command, terminate session
   - Returns: output, running, shell_id
   - Examples:
     * shell_session(shell_id="shell_123")
     * shell_session(shell_id="shell_123", action="terminate")

4. execute_code - Execute code (Python or JavaScript)
   - When to use: run short code snippets, test expressions
   - Returns: output, error, exit_code, execution_time
   - Examples:
     * execute_code(code="print(2+2)")
     * execute_code(code="console.log(2+2)", language="javascript")

【NOT available as tools — use execute_shell_command instead】:
- get_working_directory → execute_shell_command(command="cd")
- change_directory → execute_shell_command(command="cd /path && command")
- check_path_exists → use list_directory or read_text_file instead

【Tool Call Examples】:
Example 1: 列出目录
{"thought": "用户要列出D盘文件", "reasoning": "使用execute_shell_command执行dir命令", "tool_name": "execute_shell_command", "tool_params": {"command": "dir", "cwd": "D:\\project"}}

Example 2: 检查命令可用性
{"thought": "用户想知道git是否可用", "reasoning": "使用find_command检查git", "tool_name": "find_command", "tool_params": {"command": "git"}}

Example 3: 运行代码
{"thought": "用户要运行Python代码", "reasoning": "使用execute_code执行", "tool_name": "execute_code", "tool_params": {"code": "print('hello')"}}

Example 4: 任务完成
{"thought": "命令执行完毕", "reasoning": "结果已返回", "tool_name": "finish", "tool_params": {"result": "已列出目录内容：..."}}
"""
    

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此Shell命令任务，按以下步骤：
1. 确认命令可用性（使用find_command）
2. 执行命令，设置合适的超时和工作目录
3. 用中文报告执行结果"""

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.SHELL)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ cmd / script / shell_cmd (correct: command)\n"
            "- ❌ directory / dir (correct: cwd)\n"
            "- ❌ id / session / sid (correct: shell_id)"
        )
        return auto_reminder + forbidden

    def get_safety_reminder(self) -> str:
        return "⚠️ Shell Safety: Destructive commands (rm/del/format/rmdir) require extra caution. Confirm before execution."

    def get_rollback_instructions(self) -> str:
        return """If a command fails:
1. Check if the command is available (use find_command)
2. Check if the working directory is correct (use execute_shell_command with cwd parameter)
3. For destructive commands, verify the target before execution"""
