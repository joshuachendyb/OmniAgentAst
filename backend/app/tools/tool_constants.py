# -*- coding: utf-8 -*-
"""
【工具层常量】— 工具函数运行时常量集中管理 — 北京老陈 2026-05-30

定义：执行具体工具的执行层。
文件：app/tools/network/http_request.py、app/tools/tool_error_classifier.py、
      app/services/agent/tool_retry_engine.py
职责：执行工具、捕获工具异常、判断工具能否重试
错误分类器：ToolErrorClassifier（不看 HTTP 状态码数字，只看异常类型名。
  HTTPStatusError → 不管 400/429/500 → 统一归为 ToolErrorCategory.NETWORK）

所有工具函数本身运行时需要的常量统一定义在此。
与系统层常量文件 constants.py 严格分开，两层互不引用。

分层原则：
  - 本文件（tool_constants.py）：工具层。TOOL_HTTP_* 是工具自己判断重试用的拷贝，
    TOOL_TIMEOUTS 等是工具运行参数。不引用 constants.py 的系统层 SYS_HTTP_*。
  - constants.py：系统层。SYS_HTTP_* 是 HTTP 协议事实定义，
    供 SystemErrorClassifier 和 LLM 客户端使用。

禁止：
  ❌ 本文件 import constants.py 的任何内容
  ❌ 本文件的常量被系统层代码引用（系统层应引用 constants.py 的 SYS_* 常量）
"""

# ============================================================
# 1. 工具超时配置(从 tool_meta.py 迁移) — 【工具层】
#    用于工具内部校验 deadline、ToolRetryEngine 保险丝超时。
#    与系统层的 SYS_DEFAULT_LLM_TIMEOUT（LLM 客户端超时）完全无关。
# ============================================================

TOOL_TIMEOUTS = {
    # 双重用途：
    # 1. 工具内部校验 deadline / subprocess.run 超时
    # 2. ToolRetryEngine 用 asyncio.wait_for(timeout=此值) 做保险丝，
    #    防止工具卡死不返回。详见 tool_retry_engine.py 第95行。
    # 警告：修改此值会影响重试引擎的超时行为。
    "list_directory": 30,
    "search_files": 120,
    "grep_file_content": 120,
    "read_media_file": 60,
    "edit_text_file": 60,
    "archive_tool": 120,
    "read_config_file": 30,
    "write_config_file": 30,
    "execute_shell_command": 120,
    "execute_shell_command_foreground": 120,
    "execute_shell_command_background": 10,
    "execute_python": 300,
    "execute_javascript": 300,
    "shell_session": 60,

    "event_log": 60,

    "search_web": 60,
    "http_request": 60,
    "download_file": 120,
    "fetch_webpage": 60,
    "network_diagnose": 60,
    "window_info": 20,
    "window_focus": 20,
    "window_resize": 20,
    "window_maximize": 20,
    "window_minimize": 20,
    "window_restore": 20,
    "window_topmost": 20,
    "window_unpin": 20,
    "mouse_click": 20,
    "mouse_move": 20,
    "mouse_scroll": 20,
    "mouse_position": 10,
    "clipboard_read": 10,
    "clipboard_write": 10,
    "time_now": 10,
    "time_add": 10,
    "time_diff": 10,
    "query_calendar": 30,
    "timer": 60,
    "timer_set": 10,
    "timer_clear": 10,
    "timer_list": 10,
    "default": 120,
}

# ============================================================
# 1.1 Subprocess/HTTP超时配置(从各工具文件硬编码迁移)— 北京老陈 2026-05-31
# 【工具层】工具执行 subprocess/httpx 的硬超时阈值。
#     系统层的 SYS_DEFAULT_CONNECT_TIMEOUT 等是 LLM 客户端超时，与本段无关。
# ============================================================

# subprocess执行超时(秒)
SUBPROCESS_TIMEOUT_DEFAULT = 10    # 通用subprocess执行超时
SUBPROCESS_TIMEOUT_SHORT = 5       # 短时subprocess(shell communicate、代码执行)
SUBPROCESS_TIMEOUT_VERY_SHORT = 3  # 极短subprocess(process wait)
SUBPROCESS_TIMEOUT_LONG = 60       # 长时subprocess(文档转换等耗时操作)

# httpx请求超时(秒)
HTTPX_TIMEOUT_DEFAULT = 5.0        # 通用httpx请求超时

# ============================================================
# 2. 文件工具配置(从 file_tools.py 迁移) — 小欧 2026-06-18 新增FILE_OPERATION_TOOLS
# 【工具层】文件工具运行时的参数。仅工具代码使用。
# ============================================================

FILE_OPERATION_TOOLS = {
    "read_text_file", "write_text_file", "edit_text_file",
    "move_file", "copy_file", "delete_file", "rename_file",
    "compress_files", "extract_archive",
}

READ_FILE_DEFAULT_LIMIT = 500
DEFAULT_PAGE_SIZE = 200

MAX_PAGE_SIZE = 500
MAX_READ_SIZE = 10 * 1024 * 1024
MAX_MEDIA_READ_SIZE = 50 * 1024 * 1024
MAX_BATCH_FILE_COUNT = 100
MAX_SEARCH_FILE_SIZE = 10 * 1024 * 1024
MAX_SEARCH_RESULTS = 1000

# 二进制文件扩展名 — 小健 2026-06-24 更新：补充媒体扩展名
# 用途：read_text_file/write_text_file/edit_text_file等文本工具拒绝二进制文件
# 说明：包含所有二进制格式（包括系统不支持的.rar/.7z），用于防止文本工具误操作二进制文件
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tiff', '.tif', '.svg',
    '.heic', '.heif',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4a', '.ogg',
    '.flac', '.aac', '.wma', '.mid', '.midi', '.webm',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
    '.exe', '.msi', '.dll', '.so', '.dylib',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf',
    '.odt', '.ods', '.odp', '.rtf',
}

# ============================================================
# 3. 工具注册模块映射(从 lazy_loader.py 迁移) — 【工具层】
# ============================================================

CATEGORY_MODULES = {
    "file": ("app.tools.file", "_register_file_tools"),
    "shell": ("app.tools.shell", "_register_shell_tools"),
    "network": ("app.tools.network", "_register_network_tools"),
    "system": ("app.tools.system", "_register_system_tools"),
    "desktop": ("app.tools.desktop", "_register_desktop_tools"),
    "document": ("app.tools.document", "_register_document_tools"),
    "dataanalysis": ("app.tools.dataanalysis", "_register_dataanalysis_tools"),
    "fundamental": ("app.tools.fundamental", "_register_fundamental_tools"),
    "win_registry": ("app.tools.win_registry", "_register_registry_tools"),
    "timer": ("app.tools.timer", "_register_timer_tools"),
}

# ============================================================
# 4. 网络工具配置(从 http_client_sdk.py 迁移) — 【工具层】
#    网络工具的 httpx 客户端连接池参数。与系统层的 LLM_MAX_CONNECTIONS（LLM 客户端）分开。
# ============================================================

DEFAULT_TIMEOUT_SEC = 30.0
NETWORK_MAX_CONNECTIONS = 100
NETWORK_MAX_KEEPALIVE = 20

# ============================================================
# 6. 注册表工具映射(从 reg_tools.py 迁移) — 【工具层】
# ============================================================

HIVE_MAP = {
    "HKCU": "HKEY_CURRENT_USER",
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}

# ============================================================
# 7. 工具内容质量(从 content_quality.py 迁移) — 【工具层】
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
# 8. 工具安全模式(从 shell_helper/exec_helper 迁移) — 【工具层】
# ============================================================

# DANGEROUS_PATTERNS 已于 2026-06-27 删除
# 原因：execute_code改用execute_code_safety.py的分级检查(RISK_CHECK_RULES)，
#        tool_safety_checker改用execute_shell_command_safety.py的分级检查(SHELL_DANGEROUS_PATTERNS)，
#        DANGEROUS_PATTERNS（Python模式）无人引用，删除。

# SHELL_DANGEROUS_PATTERNS 已于 2026-06-27 迁出到 execute_shell_command_safety.py
# 原因：规则与检查逻辑内聚（对齐execute_code_safety.py设计原则），不再放在全局常量文件



# ============================================================
# 9. 工具日期/哈希辅助(从 date_helper/hash_helper 迁移) — 【工具层】
# ============================================================

QINGMING_DATES = {
    2024: (4, 4), 2025: (4, 4), 2026: (4, 5),
    2027: (4, 5), 2028: (4, 4), 2029: (4, 5), 2030: (4, 5),
    2031: (4, 5), 2032: (4, 4), 2033: (4, 4), 2034: (4, 5), 2035: (4, 5),
}

SUPPORTED_ALGORITHMS = {"md5", "sha1", "sha256", "sha512"}

# ============================================================
# 10. 工具重试配置(从 tool_config.py 迁移) — 【工具层】
#    工具重试引擎（ToolRetryEngine）运行时参数。
#    与系统层的 LLM 熔断/重试策略完全分开。
# ============================================================

TOOL_RETRY_BACKOFF = {
    "default": 2.0,
}

# 工具层 HTTP 可重试状态码 — 小欧 2026-06-30
# 用途：http_request 等 network 工具判断是否抛异常给 ToolRetryEngine 重试。
#       与系统层 constants.py 的 SYS_RATE_LIMIT_CODES（LLM 限流检测）完全无关。
TOOL_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "authorization", "credential"}

# ============================================================
# 11. 系统敏感路径黑名单(从 path_validator 迁移) — 小健 2026-06-23
# 【工具层】path_validator 的工具级安全检查路径，防止误写系统关键文件。
# ============================================================

FORBIDDEN_PATHS_EXACT = {
    "/etc/shadow",
    "/etc/sudoers",
}

FORBIDDEN_PATHS_PREFIX = {
    "/proc",
    "/sys",
}

FORBIDDEN_PATHS_WINDOWS_EXACT = {
    r"C:\Windows\System32\config\SAM",
    r"C:\Windows\System32\config\SYSTEM",
    r"C:\Windows\System32\config\SECURITY",
    r"C:\Windows\System32\config\SOFTWARE",
    r"C:\Windows\System32\config\DEFAULT",
}

FORBIDDEN_PATHS_WINDOWS_PREFIX = {
    r"C:\Windows\System32\config",
    r"C:\Windows\WinSxS",
}
