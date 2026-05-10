# -*- coding: utf-8 -*-
"""
工具元数据统一管理 - 小健 2026-05-02

集中管理工具运行时配置（超时、分类等），
从各个散落的文件中收归一处。

Pydantic模型（file_schema.py等）负责：参数定义、类型、默认值、required
本文件负责：运行时配置（模型不包含的信息）
"""


TOOL_TIMEOUTS = {
    "write_file": 30,
    "write_text_file": 30,
    "delete_file": 30,
    "move_file": 30,
    "rename_file": 30,
    "list_directory": 10,
    "create_directory": 10,
    "get_file_info": 10,
    "get_directory_tree": 30,
    "search_files": 60,
    "grep_file_content": 60,
    "read_text_file": 30,
    "read_media_file": 30,
    "read_batch_file": 60,
    "precise_replace_in_file": 30,
    "edit_file": 30,
    "generate_report": 15,
    "compare_files": 30,
    "batch_rename": 30,
    "compress_files": 60,
    "file_monitor": 30,
    "file_statistics": 30,
    "file_checksum": 30,
    "list_allowed_directories": 5,
    "execute_command": 120,
    "run_command": 120,
    "get_current_time": 5,
    "get_system_info": 10,
    # system/工具超时配置 小沈-2026-05-05
    "net_connections": 15,
    "event_log": 30,
    "list_processes": 10,
    "kill_process": 10,
    "log_message": 5,
    "get_logs": 30,
    "service_list": 10,
    "service_start": 60,
    "service_stop": 60,
    "task_list": 10,
    "task_create": 30,
    "task_delete": 10,
    # time/工具超时配置 小沈-2026-05-05
    "get_current_time": 5,
    "time_format": 5,
    "time_diff": 5,
    "timer_set": 30,
    "timer_clear": 5,
    "time_utc_to_local": 5,
    "time_local_to_utc": 5,
    "time_is_weekend": 5,
    "time_is_holiday": 15,
    "time_add": 5,
    "timer_list": 5,
    "time_compare": 5,
    "time_to_timestamp": 5,
    "timestamp_to_time": 5,
    "time_is_workday": 10,
    "time_next_n_workday": 10,
    # network/工具超时配置 小沈-2026-05-07
    "search_web": 25,
    "http_request": 30,
    "download_file": 60,
    "fetch_webpage": 30,
    "ping": 15,
    "port_check": 10,
    "default": 60,
}


def get_timeout(tool_name: str) -> int:
    """获取工具超时时间（秒）"""
    return TOOL_TIMEOUTS.get(tool_name, TOOL_TIMEOUTS["default"])
