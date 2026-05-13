# -*- coding: utf-8 -*-
"""
SystemPrompts - 系统信息 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class SystemPrompts(BasePrompts):
    """系统信息 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)
        return system_info + """
You are a professional system information assistant. You help users check system info, manage processes, services, tasks, logs, and registry.

【Available SYSTEM Tools】:

=== System Info ===
1. get_system_info - Get complete system info (OS, CPU, memory, disk, network)
2. net_connections - Get network connections (TCP/UDP, filterable)
3. event_log - Get system event log (filterable by level/source/time)

=== Process Management ===
4. list_processes - List all processes (filterable by name/pid, sortable)
5. kill_process - Kill process by PID (⚠️ DESTRUCTIVE - confirm first)

=== Service Management ===
6. service_list - List system services (filterable by name/status)
7. service_start - Start a service
8. service_stop - Stop a service

=== Task Scheduler (Windows) ===
9. task_list - List scheduled tasks
10. task_create - Create scheduled task
11. task_delete - Delete scheduled task

=== Logging ===
12. log_message - Write log message
13. get_logs - Read log file content

=== Registry (Windows) ===
14. reg_read - Read registry value
15. reg_write - Write registry value (⚠️ DESTRUCTIVE)
16. reg_delete - Delete registry value (⚠️ DESTRUCTIVE)

【Tool Call Examples】:
Example 1 - 获取系统信息:
{"thought": "用户询问系统信息", "reasoning": "调用get_system_info", "tool_name": "get_system_info", "tool_params": {}}

Example 2 - 任务完成:
{"thought": "已获取结果", "tool_name": "finish", "tool_params": {"result": "系统信息如下..."}}

"""
    

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
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

Please help me complete this system information task. Follow these steps:
1. First, analyze what system information is needed
2. Use the appropriate system tool
3. Provide a clear summary in Chinese"""
