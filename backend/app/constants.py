# -*- coding: utf-8 -*-
"""
系统常量集中管理 — 小健 2026-05-24

所有跨模块共享的常量统一定义在此，消除散落和重复。
按功能分组：HTTP/错误码、重试/限流、网络/超时、内容截断、错误类型。
"""

# ============================================================
# 1. HTTP 状态码与错误码
# ============================================================

HTTP_RATE_LIMIT = 429
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_GATEWAY_TIMEOUT = 504
HTTP_TIMEOUT_BROKEN = 524

RATE_LIMIT_STATUS_CODES = {HTTP_RATE_LIMIT, 1305}

RETRYABLE_HTTP_STATUS_CODES = {HTTP_RATE_LIMIT, HTTP_INTERNAL_ERROR, HTTP_BAD_GATEWAY, HTTP_SERVICE_UNAVAILABLE, HTTP_GATEWAY_TIMEOUT}

# ============================================================
# 2. 重试与限流
# ============================================================

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0
DEFAULT_BACKOFF_FACTOR = 2.0

DEFAULT_RETRYABLE_ERRORS = ["timeout", "network_error"]

CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60.0
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = 3

# ============================================================
# 3. 网络与超时
# ============================================================

DEFAULT_LLM_TIMEOUT = 60
DEFAULT_CONNECT_TIMEOUT = 30.0
DEFAULT_WRITE_TIMEOUT = 10.0
DEFAULT_POOL_TIMEOUT = 10.0
DEFAULT_PROBE_TIMEOUT = 15
DEFAULT_API_TEST_TIMEOUT = 30.0

LLM_MAX_CONNECTIONS = 10
LLM_MAX_KEEPALIVE = 5
API_TEST_MAX_CONNECTIONS = 5
API_TEST_MAX_KEEPALIVE = 2
NETWORK_TOOL_MAX_CONNECTIONS = 100
NETWORK_TOOL_MAX_KEEPALIVE = 20

BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

# ============================================================
# 4. 内容截断与字符限制
# ============================================================

MAX_CONTEXT_CHARS = 150000
TEMP_HISTORY_CHAR_LIMIT = 50000
OBSERVATION_BUDGET_DECAY = 10000
OBSERVATION_BUDGET_MIN = 20000
OBSERVATION_BUDGET_MAX = 50000

DEFAULT_MAX_OUTPUT_CHARS = 5000
DEFAULT_MAX_FILE_CHARS = 8000
DEFAULT_MAX_DOC_CHARS = 10000
DEFAULT_MAX_CLIPBOARD_CHARS = 5000
DEFAULT_MAX_ENV_VALUE_CHARS = 1000
DEFAULT_MAX_DATA_CHARS = 1000000
DEFAULT_MAX_LIST_ITEMS = 10000

MAX_CHUNK_COUNT = 5000
MAX_EMPTY_CONTENT_COUNT = 100
LOG_PREVIEW_CHARS = 500
DATA_TOO_LARGE_THRESHOLD = 10000

# ============================================================
# 5. 错误类型常量
# ============================================================

ERROR_TYPE_NETWORK_ERROR = "network_error"
ERROR_TYPE_TIMEOUT = "timeout"
ERROR_TYPE_IDLE_TIMEOUT = "idle_timeout"
ERROR_TYPE_RATE_LIMIT = "rate_limit"
ERROR_TYPE_EMPTY_RESPONSE = "empty_response"
ERROR_TYPE_RETRY_FAILED = "retry_failed"
ERROR_TYPE_THOUGHT_ONLY = "thought_only"
ERROR_TYPE_JSON_PARSE_ERROR = "json_parse_error"
ERROR_TYPE_API_LIMIT = "api_limit"
ERROR_TYPE_DATA_TOO_LARGE = "data_too_large"
ERROR_TYPE_UNKNOWN = "unknown"

API_ERROR_PREFIX = "api_error_"
API_ERROR_429 = "api_error_429"
API_ERROR_400 = "api_error_400"
API_ERROR_401 = "api_error_401"
API_ERROR_403 = "api_error_403"
API_ERROR_500 = "api_error_500"
API_ERROR_502 = "api_error_502"
API_ERROR_503 = "api_error_503"
API_ERROR_504 = "api_error_504"
API_ERROR_524 = "api_error_524"

# ============================================================
# 6. HTTP状态码 → 错误类型 映射表
# ============================================================

HTTP_STATUS_TO_ERROR_TYPE = {
    HTTP_RATE_LIMIT: API_ERROR_429,
    HTTP_SERVICE_UNAVAILABLE: API_ERROR_503,
    HTTP_TIMEOUT_BROKEN: API_ERROR_524,
    HTTP_INTERNAL_ERROR: API_ERROR_500,
    HTTP_BAD_GATEWAY: API_ERROR_502,
    HTTP_GATEWAY_TIMEOUT: API_ERROR_504,
    HTTP_UNAUTHORIZED: API_ERROR_401,
    HTTP_FORBIDDEN: API_ERROR_403,
    HTTP_BAD_REQUEST: API_ERROR_400,
}

# ============================================================
# 7. 错误类型 → (错误分类, 用户消息) 映射表
# 遵循 doc-react步骤/Omni－后端系统错误分类处理的设计方案-小沈-2026-04-10.md
# ============================================================

ERROR_TYPE_MAP = {
    "idle_timeout": ("timeout", "请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试"),
    "timeout_error": ("timeout", "请求超时，请重试"),
    "read_error": ("server", "读取响应失败，请重试"),
    "connect_error": ("connect", "连接失败，请检查网络"),
    "protocol_error": ("protocol", "协议错误，请重试"),
    "proxy_error": ("protocol", "代理错误，请检查网络配置"),
    "write_error": ("server", "发送请求失败"),
    "network_error": ("network", "网络错误，请检查网络连接"),
    API_ERROR_503: ("api_error", "AI服务渠道不可用 (errorcode=503)，请检查API配置或更换模型"),
    API_ERROR_524: ("api_error", "AI服务已超载 (errorcode=524)，请更换模型或稍后重试"),
    API_ERROR_429: ("api_error", "API请求过于频繁 (errorcode=429)，请稍后再试或更换模型"),
    API_ERROR_401: ("security", "API认证失败 (errorcode=401)，请检查API密钥配置"),
    API_ERROR_403: ("security", "API访问被拒绝 (errorcode=403)，请检查API权限配置"),
    API_ERROR_400: ("validation", "API请求参数错误 (errorcode=400)，请检查输入内容"),
    API_ERROR_500: ("server", "AI服务内部错误 (errorcode=500)，请稍后重试或更换模型"),
    API_ERROR_502: ("server", "AI服务网关错误 (errorcode=502)，请稍后重试"),
    API_ERROR_504: ("timeout", "AI服务响应超时 (errorcode=504)，请稍后重试"),
    "unknown": ("server", "AI服务暂无响应，请稍后重试"),
    "empty_response": ("server", "AI服务返回空响应，请稍后重试"),
}

# ============================================================
# 8. httpx异常类型 → ERROR_TYPE_MAP键名 映射表
# ============================================================

# ============================================================
# 9. CRSS评分常量
# ============================================================

CRSS_DANGEROUS_COMMAND_BONUS = 3.0  # 危险命令额外加分
CRSS_ACTION_MODULATION_FACTOR = 0.3  # 动作兼容调制因子
CRSS_ACTION_INFERENCE_WEIGHT = 0.5  # 动作推类型权重

HTTPX_EXCEPTION_TO_ERROR_KEY = {
    "ConnectError": "connect_error",
    "ProtocolError": "protocol_error",
    "ProxyError": "proxy_error",
    "TimeoutException": "timeout_error",
    "ReadError": "read_error",
    "WriteError": "write_error",
    "NetworkError": "network_error",
}
