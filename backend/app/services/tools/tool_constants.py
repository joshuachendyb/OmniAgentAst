# -*- coding: utf-8 -*-
"""
工具函数运行时常量集中管理 — 北京老陈 2026-05-30

所有工具函数本身运行时需要的常量统一定义在此。
"""

# ============================================================
# 1. 工具超时配置（从 tool_meta.py 迁移）
# ============================================================

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

# ============================================================
# 2. 文件工具配置（从 file_tools.py 迁移）
# ============================================================

READ_FILE_DEFAULT_LIMIT = 500
DEFAULT_PAGE_SIZE = 200
PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
MAX_READ_SIZE = 10 * 1024 * 1024
MAX_MEDIA_READ_SIZE = 50 * 1024 * 1024
MAX_BATCH_FILE_COUNT = 100
MAX_SEARCH_FILE_SIZE = 10 * 1024 * 1024

BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tiff', '.tif',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4a', '.ogg',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
    '.exe', '.msi', '.dll', '.so', '.dylib',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf',
}

# ============================================================
# 3. 工具注册模块映射（从 lazy_loader.py 迁移）
# ============================================================

CATEGORY_MODULES = {
    "file": ("app.services.tools.file", "_register_file_tools"),
    "shell": ("app.services.tools.shell", "_register_shell_tools"),
    "network": ("app.services.tools.network", "_register_network_tools"),
    "system": ("app.services.tools.system", "_register_system_tools"),
    "desktop": ("app.services.tools.desktop", "_register_desktop_tools"),
    "document": ("app.services.tools.document", "_register_document_tools"),
    "meta": ("app.services.tools.meta", "_register_meta_tools"),
}

# ============================================================
# 4. 网络工具配置（从 http_client_sdk.py 迁移）
# ============================================================

DEFAULT_TIMEOUT_SEC = 30.0
NETWORK_MAX_CONNECTIONS = 100
NETWORK_MAX_KEEPALIVE = 20

# ============================================================
# 6. 注册表工具映射（从 reg_tools.py 迁移）
# ============================================================

HIVE_MAP = {
    "HKCU": "HKEY_CURRENT_USER",
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}

# ============================================================
# 7. 工具内容质量（从 content_quality.py 迁移）
# ============================================================

SELF_REF_KEYWORDS = [
    '已成功', '需要继续', '现在需要', '接下来将', '按照要求',
    '继续创建', '已完成', '已创建', '写入成功', '已经写入',
    '已成功创建', '内容已写入', '成功写入', '已成功写入',
    '现在应该', '接下来需要', '需要先', '然后需要',
]

CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.go', '.c', '.cpp', '.rs', '.rb', '.swift', '.kt', '.scala'}
DOC_EXTENSIONS = {'.txt', '.md', '.doc', '.docx', '.csv', '.log', '.ini', '.cfg', '.yml', '.yaml', '.json', '.xml', '.html', '.htm', '.css', '.scss', '.less'}

SELF_REF_THRESHOLD_NORMAL = 0.6
SELF_REF_THRESHOLD_SHORT = 0.4
SHORT_CONTENT_LENGTH = 50

# ============================================================
# 8. 工具安全模式（从 shell_helper/exec_helper 迁移）
# ============================================================

SHELL_INJECTION_PATTERNS = [
    (r'\$\(', '子shell执行 $()'),
    (r'`[^`]*`', '命令替换反引号'),
]

DANGEROUS_PATTERNS = [
    (r"os\.system\s*\(", "系统调用(os.system)"),
    (r"subprocess\.(call|run|Popen|check_output)\s*\(", "子进程调用(subprocess)"),
    (r"shutil\.rmtree\s*\(", "递归删除目录(shutil.rmtree)"),
    (r"os\.remove\s*\(", "删除文件(os.remove)"),
    (r"os\.unlink\s*\(", "删除文件(os.unlink)"),
    (r"__import__\s*\(", "动态导入(__import__)"),
    (r"eval\s*\(", "动态执行(eval)"),
    (r"exec\s*\(", "动态执行(exec)"),
    (r"compile\s*\(", "动态编译(compile)"),
    (r"open\s*\(.*[\'\"]w[\'\"]", "写入文件操作"),
    (r"socket\s*\.", "网络Socket操作"),
    (r"requests\.(get|post|put|delete|patch)\s*\(", "HTTP请求(requests)"),
    (r"urllib\.request", "URL请求(urllib)"),
]

# ============================================================
# 9. 工具日期/哈希辅助（从 date_helper/hash_helper 迁移）
# ============================================================

QINGMING_DATES = {
    2024: (4, 4), 2025: (4, 4), 2026: (4, 5),
    2027: (4, 5), 2028: (4, 4), 2029: (4, 5), 2030: (4, 5),
    2031: (4, 5), 2032: (4, 4), 2033: (4, 4), 2034: (4, 5), 2035: (4, 5),
}

SUPPORTED_ALGORITHMS = {"md5", "sha1", "sha256", "sha512"}

# ============================================================
# 10. 工具重试配置（从 tool_config.py 迁移）
# ============================================================

TOOL_RETRY_MAX = {
    "default": 3,
}

TOOL_RETRY_BACKOFF = {
    "default": 2.0,
}

TOOL_RETRYABLE_ERRORS = {
    "default": ["timeout"],
}
