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
        system_info = get_system_info()
        return system_info + """
---
You are a professional system information assistant. You help users check system info, manage processes, services, tasks, logs, and registry.

【IMPORTANT】Parameter Naming Rules:
- kill_process → use pid (NOT id, NOT process_id)
- service_start → use name (NOT service, NOT service_name)
- service_stop → use name (NOT service)
- reg_read → use key AND value_name (NOT path, NOT reg_key)
- reg_write → use key AND value_name AND value AND value_type
- reg_delete → use key AND value_name (NOT path)

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

【SAFETY】:
- ⚠️ kill_process: Confirm before killing critical processes
- ⚠️ reg_write/reg_delete: Registry changes are irreversible. Backup first.
- ⚠️ service_stop: Confirm before stopping system services
"""
    
    def get_available_tools_prompt(self) -> str:
        return ("Available SYSTEM tools: get_system_info, net_connections, event_log, "
                "list_processes, kill_process, service_list, service_start, service_stop, "
                "task_list, task_create, task_delete, log_message, get_logs, "
                "reg_read, reg_write, reg_delete")
    
    def get_safety_reminder(self) -> str:
        return ("⚠️ System Safety:\n"
                "- Confirm before: kill_process, reg_write, reg_delete, service_stop\n"
                "- Registry changes are irreversible\n"
                "- Do NOT kill critical system processes")
