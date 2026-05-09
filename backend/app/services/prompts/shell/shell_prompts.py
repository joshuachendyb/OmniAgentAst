# -*- coding: utf-8 -*-
"""
ShellPrompts - Shell命令执行 Prompt模板

P0优先级：参数易混淆（command/cmd/script），安全风险高

Author: 小健 - 2026-05-06
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

【Available SHELL Tools】:

=== P0 - Core Tools ===

1. execute_shell_command - Execute command in shell environment
   - Returns: {stdout, stderr, exit_code, working_dir}
   - Example: execute_shell_command(command="dir D:\\project")
   - ⚠️ SECURITY: Destructive commands (rm/del/format) require extra caution.

2. get_working_directory - Get current working directory
   - No parameters needed
   - Example: get_working_directory()

3. change_directory - Change current working directory
   - Example: change_directory(path="D:\\project")

=== P1 - Path & Command Tools ===

4. check_path_exists - Check if path exists
   - Example: check_path_exists(path="C:\\Users")

5. check_command_available - Check if command is available
   - Example: check_command_available(command="python")

6. locate_command - Find all paths of a command
   - Example: locate_command(command="node")

=== P2 - Background Shell Tools ===

7. get_shell_output - Get output from background shell session
   - Example: get_shell_output(session_id="shell_123")

8. terminate_shell - Terminate background shell session
   - Example: terminate_shell(session_id="shell_123")

【Tool Call Examples】:

Example 1: List directory (Windows)
{
    "thought": "用户要列出D盘project目录的文件",
    "reasoning": "使用execute_shell_command执行dir命令",
    "tool_name": "execute_shell_command",
    "tool_params": {"command": "dir D:\\project"}
}

Example 2: Run Python script
{
    "thought": "用户要运行main.py",
    "reasoning": "使用execute_shell_command执行python命令",
    "tool_name": "execute_shell_command",
    "tool_params": {"command": "python D:\\project\\main.py", "working_dir": "D:\\project"}
}

Example 3: Check command availability
{
    "thought": "用户想知道git是否可用",
    "reasoning": "使用check_command_available检查git",
    "tool_name": "check_command_available",
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
1. First, check if the command is available
2. Execute the command with appropriate timeout
3. Provide a clear summary of the result"""

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.SHELL)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ cmd / script / shell_cmd (correct: command)\n"
            "- ❌ directory / dir / cwd (correct: working_dir or path)\n"
            "- ❌ id / session / sid (correct: session_id)"
        )
        return auto_reminder + forbidden

    def get_safety_reminder(self) -> str:
        return (
            "⚠️ Shell Safety:\n"
            "- Destructive commands (rm/del/format/rmdir) require extra caution\n"
            "- Always check command availability before execution\n"
            "- Use timeout to prevent hanging commands\n"
            "- Verify working directory before relative path operations"
        )

    def get_rollback_instructions(self) -> str:
        return """If a command fails:
1. Check if the command is available (use check_command_available)
2. Check if the working directory is correct (use get_working_directory)
3. For destructive commands, verify the target before execution"""
