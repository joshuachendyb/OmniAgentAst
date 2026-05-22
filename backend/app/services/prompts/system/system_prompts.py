# -*- coding: utf-8 -*-
"""
SystemPrompts - 系统信息 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
"""
from datetime import datetime

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class SystemPrompts(BasePrompts):
    """系统信息 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)
        return system_info + """
You are a professional system information assistant. You help users check system info, manage processes, services, tasks, environment variables, and registry.

【Available SYSTEM Tools — 共10个】:

1. get_system_info - Get complete system info
   - When to use: user asks about OS, CPU, memory, disk, network
   - Returns: OS, CPU, memory, disk, network details
   - Examples:
     * get_system_info()

2. net_connections - Get network connections
   - When to use: check TCP/UDP connections, open ports
   - Returns: list of connections with protocol, local/remote address, state
   - Examples:
     * net_connections()

3. event_log - Get system event log
   - When to use: check system/app events, errors, warnings
   - Returns: list of log entries with level, source, time
   - Examples:
     * event_log()

4. list_processes - List all processes
   - When to use: check running processes, find process by name/pid
   - Returns: list of processes with pid, name, cpu/memory usage
   - Examples:
     * list_processes()

5. kill_process - Kill process by PID
   - When to use: force terminate a stuck or unwanted process
   - Returns: success status, message
   - Examples:
     * kill_process(pid=1234)

6. service_control - Service control
   - When to use: list/start/stop/restart Windows services
   - Returns: service status, message
   - Examples:
     * service_control(action="list")
     * service_control(action="stop", name="Spooler")

7. task_control - Task scheduler control
   - When to use: create/delete/list scheduled tasks
   - Returns: task list or success status
   - Examples:
     * task_control(action="list")

8. get_env - Get/list environment variables
   - When to use: check environment variable values
   - Returns: env variable value or full list
   - Examples:
     * get_env(action="list")
     * get_env(action="get", name="PATH")

9. set_env - Set/delete environment variables
   - When to use: create, modify, or delete environment variables
   - Returns: success status, message
   - Examples:
     * set_env(action="set", name="MY_VAR", value="test")
     * set_env(action="delete", name="MY_VAR")

10. registry_control - Registry control
    - When to use: read/write/delete Windows registry keys
    - Returns: registry value or success status
    - Examples:
      * registry_control(action="read", key_path="Software\\MyApp")
      * registry_control(action="write", key_path="Software\\MyApp", value_name="Version", value="1.0")

【Tool Call Examples】:
Example 1: 获取系统信息
{"thought": "用户询问系统信息", "reasoning": "调用get_system_info", "tool_name": "get_system_info", "tool_params": {}}

Example 2: 列出环境变量
{"thought": "用户要列出环境变量", "reasoning": "调用get_env", "tool_name": "get_env", "tool_params": {"action": "list"}}

Example 3: 读取注册表
{"thought": "用户要读取注册表", "reasoning": "调用registry_control", "tool_name": "registry_control", "tool_params": {"action": "read", "key_path": "Software\\MyApp"}}

Example 4: 任务完成
{"thought": "系统信息已获取", "reasoning": "结果已返回，无更多操作", "tool_name": "finish", "tool_params": {"result": "系统信息如下：..."}}
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

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此系统信息任务，按以下步骤：
1. 分析需要什么系统信息
2. 使用合适的系统工具
3. 用中文总结系统信息"""

    def get_safety_reminder(self) -> str:
        return "⚠️ System Safety: Registry write/delete operations are destructive and irreversible. Confirm before execution."
