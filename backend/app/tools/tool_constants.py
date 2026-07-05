# -*- coding: utf-8 -*-
"""
【工具层常量】— 工具函数运行时常量集中管理 — 北京老陈 2026-05-30

定义：执行具体工具的执行层。
文件：app/tools/network/http_request.py、app/tools/tool_error_classifier.py、
      app/services/agent/tool_retry_engine.py、app/utils/sys_error_classifier.py
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
    "find": 120,
    "grep": 120,
    "readmedia": 60,
    "edittext": 60,
    "shell": 120,
    "tree": 120,
    "session": 60,

    "event_log": 60,

    "searchweb": 60,
    "httpget": 60,
    "download": 120,
    "fetchpage": 60,
    "ping_port": 60,
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
    "timenow": 10,
    "timeadd": 10,
    "timediff": 10,
    "calendar": 30,
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
    "readtext", "writetext", "edittext",
    "move", "copy", "delete", "rename",
    "compress", "extract",
}

READ_FILE_DEFAULT_LIMIT = 500
DEFAULT_PAGE_SIZE = 200
LISTDIR_PAGE_SIZE = 500

# ============================================================
# 观察截断常量（observation_formatter.py 统一使用）— 小欧 2026-07-04
#     常量集中管理，便于后续统一调整。
#     与 tool 层面的截断上限（如 READ_FILE_DEFAULT_LIMIT）相互独立。
# ============================================================
OBS_MAX_DISPLAY_ITEMS = 500       # 所有 list 类 handler 的最大条目数
OBS_MAX_STRING_LENGTH = 10000     # 单个字符串值的最大显示长度
OBS_DICT_MAX_KEYS = 100           # _format_key_value 的最大键数
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
# 用途：httpget 等 network 工具判断是否抛异常给 ToolRetryEngine 重试。
#       与系统层 constants.py 的 SYS_RATE_LIMIT_CODES（LLM 限流检测）完全无关。
TOOL_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

# 工具层错误码(从 constants.py 迁入) — 小欧 2026-06-30
# 用途：ToolRetryEngine 构建重试耗尽错误返回。
ERR_TOOL_NOT_FOUND = "ERR_TOOL_NOT_FOUND"
ERR_MISSING_PARAM = "ERR_MISSING_PARAM"
ERR_INVALID_PARAMS = "ERR_INVALID_PARAMS"
ERR_UNKNOWN = "ERR_UNKNOWN"

SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "authorization", "credential"}

# 工具层浏览器 User-Agent(从 constants.py 迁入) — 小欧 2026-06-30
TOOL_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

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

# ============================================================
# 12. 工具错误码(从 constants.py 整节迁入) — 小欧 2026-06-30
#     命名规范: ERR_{MODULE}_{PROBLEM}
#     MODULE: DOC/FILE/SHELL/META/SYSTEM/DESKTOP/NETWORK/DB/REG/TIMER/TASK/WIN/SYS_ENV/SYS_REG
#     所有工具返回的错误码统一定义在此,消除散落和命名不一致
# ============================================================

# --- 文档/格式类 ---
ERR_DOC_FORMAT_NOT_SUPPORTED = "ERR_DOC_FORMAT_NOT_SUPPORTED"
ERR_DOC_READ_JSON = "ERR_DOC_READ_JSON"
ERR_DOC_PARSE_FAILED = "ERR_DOC_PARSE_FAILED"

# --- 文件操作类 ---
ERR_FILE_NOT_FOUND = "ERR_FILE_NOT_FOUND"
ERR_FILE_EXISTS = "ERR_FILE_EXISTS"
ERR_FILE_PATH_INVALID = "ERR_FILE_PATH_INVALID"
ERR_FILE_PATH_NOT_DIR = "ERR_FILE_PATH_NOT_DIR"
ERR_FILE_DIRECTORY_NOT_FOUND = "ERR_FILE_DIRECTORY_NOT_FOUND"
ERR_FILE_READ = "ERR_FILE_READ"
ERR_FILE_READ_FAILED = "ERR_FILE_READ_FAILED"
ERR_FILE_READ_BINARY_FILE = "ERR_FILE_READ_BINARY_FILE"
ERR_FILE_READ_TOO_LARGE = "ERR_FILE_READ_TOO_LARGE"
ERR_FILE_WRITE_FAILED = "ERR_FILE_WRITE_FAILED"
ERR_FILE_REPLACE_FAILED = "ERR_FILE_REPLACE_FAILED"
ERR_FILE_SEARCH_FAILED = "ERR_FILE_SEARCH_FAILED"
ERR_FILE_RENAME_FAILED = "ERR_FILE_RENAME_FAILED"

# --- Shell/命令执行类 ---
ERR_SHELL_TIMEOUT = "ERR_SHELL_TIMEOUT"
ERR_SHELL_COMMAND_NOT_FOUND = "ERR_SHELL_COMMAND_NOT_FOUND"
ERR_SHELL_NOT_FOUND = "ERR_SHELL_NOT_FOUND"
ERR_SHELL_EXEC = "ERR_SHELL_EXEC"
ERR_SHELL_EXEC_EMPTY_CODE = "ERR_SHELL_EXEC_EMPTY_CODE"
ERR_SHELL_EXEC_INVALID_DIR = "ERR_SHELL_EXEC_INVALID_DIR"
ERR_SHELL_EXEC_NODE_NOT_FOUND = "ERR_SHELL_EXEC_NODE_NOT_FOUND"
ERR_SHELL_EXEC_PYTHON_NOT_FOUND = "ERR_SHELL_EXEC_PYTHON_NOT_FOUND"
ERR_SHELL_FIND_COMMAND = "ERR_SHELL_FIND_COMMAND"
ERR_SHELL_GET_CWD = "ERR_SHELL_GET_CWD"
ERR_SHELL_INJECTION = "ERR_SHELL_INJECTION"
ERR_SHELL_CHECK_PATH = "ERR_SHELL_CHECK_PATH"
ERR_SHELL_CHECK_RUNNING = "ERR_SHELL_CHECK_RUNNING"
ERR_SHELL_EXCEPTION = "ERR_SHELL_EXCEPTION"
ERR_SHELL_VALIDATE_COMMAND = "ERR_SHELL_VALIDATE_COMMAND"

# --- 参数/输入校验类 ---
ERR_PARAM_INVALID = "ERR_PARAM_INVALID"
ERR_PARAM_MISSING = "ERR_PARAM_MISSING"
ERR_PARAM_CONFLICT = "ERR_PARAM_CONFLICT"
ERR_PARAMETER_INVALID = "ERR_PARAMETER_INVALID"
ERR_PARAMETER_EMPTY = "ERR_PARAMETER_EMPTY"
ERR_PARAMETER_MISSING = "ERR_PARAMETER_MISSING"

# --- Meta/任务/时间类 ---
ERR_META_NO_ACTIVE_TASK = "ERR_META_NO_ACTIVE_TASK"
ERR_META_INVALID_FORMAT = "ERR_META_INVALID_FORMAT"
ERR_TASK_CREATE = "ERR_TASK_CREATE"
ERR_TASK_DELETE = "ERR_TASK_DELETE"
ERR_TASK_EMPTY = "ERR_TASK_EMPTY"
ERR_TASK_LIST = "ERR_TASK_LIST"
ERR_TASK_NOT_FOUND = "ERR_TASK_NOT_FOUND"
ERR_TIMER_SET = "ERR_TIMER_SET"
ERR_TIMER_CLEAR = "ERR_TIMER_CLEAR"
ERR_TIMER_LIST = "ERR_TIMER_LIST"
ERR_TIMER_PARAM = "ERR_TIMER_PARAM"
ERR_TIMESTAMP_TO_TIME = "ERR_TIMESTAMP_TO_TIME"
ERR_TIME_ADD = "ERR_TIME_ADD"
ERR_TIME_DATE = "ERR_TIME_DATE"
ERR_TIME_DIFF = "ERR_TIME_DIFF"
ERR_TIME_NOW = "ERR_TIME_NOW"
ERR_TIME_TO_TIMESTAMP = "ERR_TIME_TO_TIMESTAMP"
ERR_TIME_TZ = "ERR_TIME_TZ"

# --- 网络/URL类 ---
ERR_INVALID_URL = "ERR_INVALID_URL"
ERR_NETWORK_REQUEST = "ERR_NETWORK_REQUEST"
ERR_NETWORK_TIMEOUT = "ERR_NETWORK_TIMEOUT"
ERR_NETWORK_DNS = "ERR_NETWORK_DNS"
ERR_NETWORK_CONNECT = "ERR_NETWORK_CONNECT"

# --- 系统/进程/服务类 ---
ERR_SYSTEM_TIMEOUT = "ERR_SYSTEM_TIMEOUT"
ERR_SYSTEM_PROCESS_LIST = "ERR_SYSTEM_PROCESS_LIST"
ERR_SYSTEM_PROCESS_KILL = "ERR_SYSTEM_PROCESS_KILL"
ERR_SYSTEM_COMMAND_NOT_FOUND = "ERR_SYSTEM_COMMAND_NOT_FOUND"
ERR_SYSTEM_INFO = "ERR_SYSTEM_INFO"
ERR_SYSTEM_EVENT_LOG = "ERR_SYSTEM_EVENT_LOG"
ERR_SYSTEM_NET_CONN = "ERR_SYSTEM_NET_CONN"
ERR_SERVICE_LIST = "ERR_SERVICE_LIST"
ERR_SERVICE_NOT_FOUND = "ERR_SERVICE_NOT_FOUND"
ERR_SERVICE_START = "ERR_SERVICE_START"
ERR_SERVICE_STOP = "ERR_SERVICE_STOP"

# --- 系统环境变量/注册表类 ---
ERR_SYS_ENV_GET = "ERR_SYS_ENV_GET"
ERR_SYS_ENV_INVALID_ACTION = "ERR_SYS_ENV_INVALID_ACTION"
ERR_SYS_ENV_INVALID_NAME = "ERR_SYS_ENV_INVALID_NAME"
ERR_SYS_ENV_INVALID_SCOPE = "ERR_SYS_ENV_INVALID_SCOPE"
ERR_SYS_ENV_INVALID_VALUE = "ERR_SYS_ENV_INVALID_VALUE"
ERR_SYS_ENV_LIST = "ERR_SYS_ENV_LIST"
ERR_SYS_REG_INVALID_ROOT_KEY = "ERR_SYS_REG_INVALID_ROOT_KEY"
ERR_SYS_REG_KEY_NOT_FOUND = "ERR_SYS_REG_KEY_NOT_FOUND"
ERR_SYS_REG_KEY_NOT_EMPTY = "ERR_SYS_REG_KEY_NOT_EMPTY"
ERR_SYS_REG_CANNOT_DELETE_ROOT = "ERR_SYS_REG_CANNOT_DELETE_ROOT"
ERR_REG_READ_FAILED = "ERR_REG_READ_FAILED"
ERR_REG_WRITE_FAILED = "ERR_REG_WRITE_FAILED"
ERR_REG_DELETE_FAILED = "ERR_REG_DELETE_FAILED"
ERR_REG_INVALID_PARAM = "ERR_REG_INVALID_PARAM"
ERR_REG_UNSUPPORTED_TYPE = "ERR_REG_UNSUPPORTED_TYPE"
ERR_REG_VALIDATE_FAILED = "ERR_REG_VALIDATE_FAILED"

# --- 桌面/GUI类 ---
ERR_DESKTOP_NOT_FOUND = "ERR_DESKTOP_NOT_FOUND"
ERR_FOCUS_WINDOW = "ERR_FOCUS_WINDOW"
ERR_GUI_CALL = "ERR_GUI_CALL"
ERR_WINDOW_LIST = "ERR_WINDOW_LIST"
ERR_WINDOW_NOT_FOUND = "ERR_WINDOW_NOT_FOUND"
ERR_WINDOW_RESIZE = "ERR_WINDOW_RESIZE"
ERR_WINDOW_SET_STATE = "ERR_WINDOW_SET_STATE"
ERR_SCREENSHOT = "ERR_SCREENSHOT"
ERR_SCREEN_RECORD = "ERR_SCREEN_RECORD"
ERR_SCREEN_SNAPSHOT = "ERR_SCREEN_SNAPSHOT"

# --- 数据库/SQL类 ---
ERR_SQL_EXEC = "ERR_SQL_EXEC"
ERR_DB_CONNECTION = "ERR_DB_CONNECTION"

# --- 数据格式解析类 ---
ERR_PARSE_YAML = "ERR_PARSE_YAML"
ERR_PARSE_TOML = "ERR_PARSE_TOML"
ERR_PARSE_INI = "ERR_PARSE_INI"
ERR_PARSE_XML = "ERR_PARSE_XML"
ERR_PARSE_JSON = "ERR_PARSE_JSON"
ERR_PARSE_PROPERTIES = "ERR_PARSE_PROPERTIES"
ERR_INVALID_JSON = "ERR_INVALID_JSON"
ERR_WRITE_YAML = "ERR_WRITE_YAML"
ERR_WRITE_TOML = "ERR_WRITE_TOML"
ERR_WRITE_JSON = "ERR_WRITE_JSON"
ERR_WRITE_DOCX = "ERR_WRITE_DOCX"
ERR_WRITE_XLSX = "ERR_WRITE_XLSX"
ERR_WRITE_PDF = "ERR_WRITE_PDF"

# --- 数据分析类 ---
ERR_DATA_ANALYSIS = "ERR_DATA_ANALYSIS"
ERR_STATISTICS_FAILED = "ERR_STATISTICS_FAILED"
ERR_SCHEMA_FAILED = "ERR_SCHEMA_FAILED"
ERR_FILTER_INVALID = "ERR_FILTER_INVALID"

# --- Agent/工具执行类 ---
ERR_TOOL_DEPRECATED = "ERR_TOOL_DEPRECATED"
ERR_UNSAFE_CODE = "ERR_UNSAFE_CODE"

# --- 其他 ---
ERR_INVALID_ACTION = "ERR_INVALID_ACTION"
ERR_INVALID_DIRECTION = "ERR_INVALID_DIRECTION"
ERR_INVALID_MODE = "ERR_INVALID_MODE"
ERR_INVALID_STEP = "ERR_INVALID_STEP"

# --- 迁移自动补充 ---
ERR_DESKTOP_CHECK_SCREEN_SIZE = "ERR_DESKTOP_CHECK_SCREEN_SIZE"
ERR_DESKTOP_CHECK_TESSERACT = "ERR_DESKTOP_CHECK_TESSERACT"
ERR_DESKTOP_CHECK_WINDOW = "ERR_DESKTOP_CHECK_WINDOW"
ERR_DESKTOP_CLIPBOARD = "ERR_DESKTOP_CLIPBOARD"
ERR_DESKTOP_GET_MOUSE_POSITION = "ERR_DESKTOP_GET_MOUSE_POSITION"
ERR_DESKTOP_GET_WINDOW_INFO = "ERR_DESKTOP_GET_WINDOW_INFO"
ERR_DESKTOP_GET_WINDOW_POSITION = "ERR_DESKTOP_GET_WINDOW_POSITION"
ERR_DESKTOP_MOUSE_CLICK = "ERR_DESKTOP_MOUSE_CLICK"
ERR_DESKTOP_MOUSE_MOVE = "ERR_DESKTOP_MOUSE_MOVE"
ERR_DESKTOP_MOUSE_SCROLL = "ERR_DESKTOP_MOUSE_SCROLL"
ERR_DESKTOP_NOTIFICATION = "ERR_DESKTOP_NOTIFICATION"
ERR_DESKTOP_NOT_WINDOWS = "ERR_DESKTOP_NOT_WINDOWS"
ERR_DESKTOP_NO_DEPENDENCY = "ERR_DESKTOP_NO_DEPENDENCY"
ERR_DESKTOP_PLATFORM_NOT_SUPPORTED = "ERR_DESKTOP_PLATFORM_NOT_SUPPORTED"
ERR_DOC_ANALYZE_DATA = "ERR_DOC_ANALYZE_DATA"
ERR_DOC_CHART_GENERATE = "ERR_DOC_CHART_GENERATE"
ERR_DOC_CONVERT_FAILED = "ERR_DOC_CONVERT_FAILED"
ERR_DOC_DATA_FORMAT_FAILED = "ERR_DOC_DATA_FORMAT_FAILED"
ERR_DOC_DB_TABLE_NOT_FOUND = "ERR_DOC_DB_TABLE_NOT_FOUND"
ERR_DOC_FORMAT_NOT_DETECTED = "ERR_DOC_FORMAT_NOT_DETECTED"
ERR_DOC_NO_OPENPYXL = "ERR_DOC_NO_OPENPYXL"
ERR_DOC_NO_PPTX = "ERR_DOC_NO_PPTX"
ERR_DOC_QUERY_EMPTY = "ERR_DOC_QUERY_EMPTY"
ERR_DOC_READ_CSV = "ERR_DOC_READ_CSV"
ERR_DOC_READ_DOCX = "ERR_DOC_READ_DOCX"
ERR_DOC_READ_PDF = "ERR_DOC_READ_PDF"
ERR_DOC_READ_PPTX = "ERR_DOC_READ_PPTX"
ERR_DOC_READ_XLSX = "ERR_DOC_READ_XLSX"
ERR_DOC_WRITE_PPTX = "ERR_DOC_WRITE_PPTX"
ERR_EXEC_FAILED = "ERR_EXEC_FAILED"
ERR_EXEC_JS = "ERR_EXEC_JS"
ERR_EXEC_PYTHON = "ERR_EXEC_PYTHON"
ERR_EXEC_TIMEOUT = "ERR_EXEC_TIMEOUT"
ERR_FILE_BACKUP = "ERR_FILE_BACKUP"
ERR_FILE_CALCULATE_DISTRIBUTION = "ERR_FILE_CALCULATE_DISTRIBUTION"
ERR_FILE_CHECKSUM_FAILED = "ERR_FILE_CHECKSUM_FAILED"
ERR_FILE_CHECKSUM_TIMEOUT = "ERR_FILE_CHECKSUM_TIMEOUT"
ERR_FILE_CHECK_PERMISSION = "ERR_FILE_CHECK_PERMISSION"
ERR_FILE_COMPRESS_FAILED = "ERR_FILE_COMPRESS_FAILED"
ERR_FILE_CONTENT_BLOCKED = "ERR_FILE_CONTENT_BLOCKED"
ERR_FILE_CONTENT_SEARCH_FAILED = "ERR_FILE_CONTENT_SEARCH_FAILED"
ERR_FILE_COPY_FAILED = "ERR_FILE_COPY_FAILED"
ERR_FILE_CREATE_DIR = "ERR_FILE_CREATE_DIR"
ERR_FILE_DELETE_FAILED = "ERR_FILE_DELETE_FAILED"
ERR_FILE_EDIT_FAILED = "ERR_FILE_EDIT_FAILED"
ERR_FILE_ENCODING = "ERR_FILE_ENCODING"
ERR_FILE_EXTRACT = "ERR_FILE_EXTRACT"
ERR_FILE_HASH = "ERR_FILE_HASH"
ERR_FILE_INFO = "ERR_FILE_INFO"
ERR_FILE_LIST_DIR_FAILED = "ERR_FILE_LIST_DIR_FAILED"
ERR_FILE_METADATA = "ERR_FILE_METADATA"
ERR_FILE_MIME_TYPE = "ERR_FILE_MIME_TYPE"
ERR_FILE_MOVE_FAILED = "ERR_FILE_MOVE_FAILED"
ERR_FILE_MOVE_TRASH = "ERR_FILE_MOVE_TRASH"
ERR_FILE_PATH_EXISTS = "ERR_FILE_PATH_EXISTS"
ERR_FILE_PATH_NOT_FILE = "ERR_FILE_PATH_NOT_FILE"
ERR_KEYBOARD_SHORTCUT = "ERR_KEYBOARD_SHORTCUT"
ERR_KEYBOARD_TYPE = "ERR_KEYBOARD_TYPE"
ERR_KEY_COMBO = "ERR_KEY_COMBO"
ERR_META_CALENDAR_NEXT_N_WORKDAY = "ERR_META_CALENDAR_NEXT_N_WORKDAY"
ERR_META_INVALID_CHECK_TYPE = "ERR_META_INVALID_CHECK_TYPE"
ERR_META_TIME_CONVERT = "ERR_META_TIME_CONVERT"
ERR_META_TIME_FORMAT = "ERR_META_TIME_FORMAT"
ERR_MISSING_TOOL = "ERR_MISSING_TOOL"
ERR_NETWORK_CONNECTION_ERROR = "ERR_NETWORK_CONNECTION_ERROR"
ERR_NETWORK_CREATE_DIR = "ERR_NETWORK_CREATE_DIR"
ERR_NETWORK_DNS_ERROR = "ERR_NETWORK_DNS_ERROR"
ERR_NETWORK_DOWN = "ERR_NETWORK_DOWN"
ERR_NETWORK_HTTP_ERROR = "ERR_NETWORK_HTTP_ERROR"
ERR_NETWORK_INVALID_HOST = "ERR_NETWORK_INVALID_HOST"
ERR_NETWORK_INVALID_PARAM = "ERR_NETWORK_INVALID_PARAM"
ERR_NETWORK_INVALID_PATH = "ERR_NETWORK_INVALID_PATH"
ERR_NETWORK_INVALID_PORT = "ERR_NETWORK_INVALID_PORT"
ERR_NETWORK_JS_RENDER = "ERR_NETWORK_JS_RENDER"
ERR_NETWORK_REQUEST_ERROR = "ERR_NETWORK_REQUEST_ERROR"
ERR_NETWORK_WRITE_FILE = "ERR_NETWORK_WRITE_FILE"
ERR_NET_UNKNOWN = "ERR_NET_UNKNOWN"
ERR_NO_DOCX = "ERR_NO_DOCX"
ERR_NO_IMAGEIO = "ERR_NO_IMAGEIO"
ERR_NO_LIBREOFFICE = "ERR_NO_LIBREOFFICE"
ERR_NO_MATCH = "ERR_NO_MATCH"
ERR_NO_MATPLOTLIB = "ERR_NO_MATPLOTLIB"
ERR_NO_NUMPY = "ERR_NO_NUMPY"
ERR_NO_PANDAS = "ERR_NO_PANDAS"
ERR_NO_PDFPLUMBER = "ERR_NO_PDFPLUMBER"
ERR_NO_PYAUTOGUI = "ERR_NO_PYAUTOGUI"
ERR_NO_PYZIPPER = "ERR_NO_PYZIPPER"
ERR_NO_PYYAML = "ERR_NO_PYYAML"
ERR_NO_RECORD_LIB = "ERR_NO_RECORD_LIB"
ERR_NO_REPORTLAB = "ERR_NO_REPORTLAB"
ERR_NO_SCREENSHOT_LIB = "ERR_NO_SCREENSHOT_LIB"
ERR_NO_TESSERACT = "ERR_NO_TESSERACT"
ERR_NO_TOMLI = "ERR_NO_TOMLI"
ERR_NO_TOMLI_W = "ERR_NO_TOMLI_W"
ERR_OCR = "ERR_OCR"
ERR_PARAM_MISMATCH = "ERR_PARAM_MISMATCH"
ERR_PATH_INVALID = "ERR_PATH_INVALID"
ERR_PATH_NOT_FILE = "ERR_PATH_NOT_FILE"
ERR_PERMISSION_DENIED = "ERR_PERMISSION_DENIED"
ERR_PIPELINE_FAILED = "ERR_PIPELINE_FAILED"
ERR_PIPELINE_STOPPED = "ERR_PIPELINE_STOPPED"
ERR_PIPELINE_TIMEOUT = "ERR_PIPELINE_TIMEOUT"
ERR_QUERY_FAILED = "ERR_QUERY_FAILED"
ERR_READ_CSV_BASIC = "ERR_READ_CSV_BASIC"
ERR_READ_CSV_DATAFRAME = "ERR_READ_CSV_DATAFRAME"
ERR_READ_EXCEL_DATAFRAME = "ERR_READ_EXCEL_DATAFRAME"
ERR_READ_ONLY_VIOLATION = "ERR_READ_ONLY_VIOLATION"
ERR_REG_PERMISSION_DENIED = "ERR_REG_PERMISSION_DENIED"

# --- 迁移自动补充 ---
ERR_DESKTOP_NO_PYWIN32 = "ERR_DESKTOP_NO_PYWIN32"
ERR_NO_WIN10TOAST = "ERR_NO_WIN10TOAST"
ERR_NO_WIN32GUI = "ERR_NO_WIN32GUI"
