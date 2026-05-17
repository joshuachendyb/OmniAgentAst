# -*- coding: utf-8 -*-
"""
ToolHelper 模块 - 内部辅助函数集合（不暴露给LLM）

【架构规范】2026-05-02 小沈
- 本目录包含各Tool分类共用的内部辅助函数
- 这些函数不注册到tool_registry，仅供Agent内部代码调用

目录结构：
    toolhelper/
    ├── __init__.py           # 本文件
    ├── file_helpers.py       # 文件操作辅助函数（10个）
    ├── content_quality.py    # 内容质量辅助函数
    ├── db_helper.py          # 数据库辅助函数（check_db_exists等）- 小沈 2026-05-17
    ├── gui_helper.py         # GUI辅助函数（_find_window_by_title等）- 小沈 2026-05-17
    ├── network_helper.py     # 网络辅助函数（_check_network等）- 小沈 2026-05-17
    └── exec_helper.py       # 代码执行辅助函数（_check_python_available等）- 小沈 2026-05-17

Author: 小沈 - 2026-05-02
"""

from app.services.tools.toolhelper.file_helpers import (
    extract_archive,
    get_file_hash,
    ensure_directory_exists,
    check_write_permission,
    check_read_permission,
    get_file_encoding,
    get_mime_type,
    backup_file,
    move_to_trash,
    validate_command,
    check_shell_running,
)

from app.services.tools.toolhelper.db_helper import (
    check_db_exists,
)

from app.services.tools.toolhelper.gui_helper import (
    _require_gui_lib,
    _gui_safe_call,
    _get_mouse_position,
    _check_screen_size,
    _check_window_exists,
    _get_window_position,
    _check_capture_permission,
    _check_tesseract_available,
    _check_notification_permission,
    _find_window_by_title,
)

from app.services.tools.toolhelper.exec_helper import (
    _check_python_available,
    _validate_code_safety,
    _check_node_available,
    _check_module_available,
)

from app.services.tools.toolhelper.shell_helper import (
    _check_shell_injection,
    _read_stream_nonblocking,
)

from app.services.tools.toolhelper.network_helper import (
    _html_to_markdown,
    _decode_bing_redirect_url,
)

__all__ = [
    "extract_archive",
    "get_file_hash",
    "ensure_directory_exists",
    "check_write_permission",
    "check_read_permission",
    "get_file_encoding",
    "get_mime_type",
    "backup_file",
    "move_to_trash",
    "validate_command",
    "check_shell_running",
    "check_db_exists",
    "_require_gui_lib",
    "_gui_safe_call",
    "_get_mouse_position",
    "_check_screen_size",
    "_check_window_exists",
    "_get_window_position",
    "_check_capture_permission",
    "_check_tesseract_available",
    "_check_notification_permission",
    "_find_window_by_title",
    "_check_python_available",
    "_validate_code_safety",
    "_check_node_available",
    "_check_module_available",
    "_check_shell_injection",
    "_read_stream_nonblocking",
    "_html_to_markdown",
    "_decode_bing_redirect_url",
]
