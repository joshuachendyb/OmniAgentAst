# -*- coding: utf-8 -*-
"""
ShellPrompts - Shell命令执行 Prompt模板

P0优先级：参数易混淆（command/cmd/script），安全风险高

Author: 小健 - 2026-05-06
更新时间: 2026-05-17 小健 — 8→4工具降级后更新prompt
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class ShellPrompts(BasePrompts):
    """Shell命令执行 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info()
        return system_info + """
You are a professional shell command execution assistant. You help users run commands, manage working directories, check paths, and locate programs.

【Available SHELL Tools — 共4个】（2026-05-17 小健 降级后）:

=== P0 - Core Tools ===

1. execute_shell_command - Execute command in shell environment
   - Core tool for all shell operations. Use cwd parameter to specify working directory (replaces change_directory)
   - Returns: {stdout, stderr, exit_code}
   - Example: execute_shell_command(command="dir", cwd="D:\\project")
   - ⚠️ SECURITY: Destructive commands (rm/del/format) require extra caution.

2. find_command - Find command path (replaces check_command_available + locate_command)
   - Check availability: find_command(command="python") → all_paths=False (fast)
   - Find all paths: find_command(command="python", all_paths=True)
   - Example: find_command(command="python")

=== P1 - Background Shell Tools ===

3. get_shell_output - Get output from background shell session
   - Example: get_shell_output(shell_id="shell_123")

4. terminate_shell - Terminate background shell session
   - Example: terminate_shell(shell_id="shell_123")

【NOT available as tools — use execute_shell_command instead】:
- get_working_directory → execute_shell_command(command="pwd") or use cwd parameter
- change_directory → execute_shell_command(command="cd /path && command", cwd="/path")
- check_path_exists → simply attempt the operation; list_directory or read_text_file will report errors

【Tool Call Examples】:

Example 1: List directory (Windows)
{
    "thought": "用户要列出D盘project目录的文件",
    "reasoning": "使用execute_shell_command执行dir命令",
    "tool_name": "execute_shell_command",
    "tool_params": {"command": "dir", "cwd": "D:\\project"}
}

Example 2: Run Python script
{
    "thought": "用户要运行main.py",
    "reasoning": "使用execute_shell_command执行python命令",
    "tool_name": "execute_shell_command",
    "tool_params": {"command": "python main.py", "cwd": "D:\\project"}
}

Example 3: Check command availability
{
    "thought": "用户想知道git是否可用",
    "reasoning": "使用find_command检查git",
    "tool_name": "find_command",
    "tool_params": {"command": "git"}
}

Example 4: Task completed
{
    "thought": "Shell命令任务已完成",
    "reasoning": "命令执行成功，结果已返回",
    "tool_name": "finish",
    "tool_params": {"result": "已列出目录内容：..."}
}
"""
    

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Please help me execute this shell command task. Follow these steps:
1. First, check if the command is available (use find_command)
2. Execute the command with appropriate timeout and working directory
3. Provide a clear summary of the result"""

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
        return (
            "⚠️ Shell Safety:\n"
            "- Destructive commands (rm/del/format/rmdir) require extra caution\n"
            "- Always check command availability before execution (use find_command)\n"
            "- Use timeout to prevent hanging commands\n"
            "- Verify working directory before relative path operations (use cwd parameter)"
        )

    def get_rollback_instructions(self) -> str:
        return """If a command fails:
1. Check if the command is available (use find_command)
2. Check if the working directory is correct (use execute_shell_command with cwd parameter)
3. For destructive commands, verify the target before execution"""
