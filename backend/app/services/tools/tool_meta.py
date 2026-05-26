# -*- coding: utf-8 -*-
"""
工具元数据统一管理 - 小健 2026-05-02

集中管理工具运行时配置（超时、分类等），
从各个散落的文件中收归一处。

Pydantic模型（file_schema.py等）负责：参数定义、类型、默认值、required
本文件负责：运行时配置（模型不包含的信息）
"""


TOOL_TIMEOUTS = {
    "rename_file": 30,
    "list_directory": 10,
    "search_files": 60,
    "grep_file_content": 60,
    "read_media_file": 30,
    "edit_file": 30,
    "archive_tool": 60,
    "execute_shell_command": 35,
    "execute_python": 120,
    "execute_javascript": 120,
    "shell_session": 30,
    "net_connections": 15,
    "event_log": 30,
    "list_processes": 10,
    "kill_process": 10,
    "service_control": 60,
    "task_control": 30,
    "search_web": 25,
    "http_request": 30,
    "download_file": 60,
    "fetch_webpage": 30,
    "network_diagnose": 30,
    "get_time": 5,
    "time_add": 5,
    "time_diff": 5,
    "query_calendar": 15,
    "timezone_convert": 5,
    "timer": 30,
    "default": 60,
}


def get_timeout(tool_name: str) -> int:
    """获取工具超时时间（秒）"""
    return TOOL_TIMEOUTS.get(tool_name, TOOL_TIMEOUTS["default"])
