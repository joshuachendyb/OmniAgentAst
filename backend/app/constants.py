# -*- coding: utf-8 -*-
"""
【系统层常量】系统常量集中管理 — 小健 2026-05-24

定义：负责 LLM 通信、Agent 循环、API 服务的基础设施层。
文件：app/services/llm/base_service.py、app/utils/error_classifier.py
职责：调 LLM API、处理 LLM 返回结果、管理 Agent 循环、SSE 流
错误分类器：SystemErrorClassifier（按异常消息字符串判断，返回 SystemErrorCategory 枚举）

系统层常量包括：HTTP 协议定义、LLM 客户端配置、Agent 循环参数、共享错误码（ERR_*）等。
与工具层常量文件 tool_constants.py 严格分开，两层互不引用。

分层原则：
  - 本文件（constants.py）：系统层。SYS_HTTP_* 是 HTTP 协议事实定义（如 429=限流），
    供 SystemErrorClassifier 和 LLM 客户端使用。SYS_DEFAULT_LLM_TIMEOUT 等是 LLM 客户端超时。
  - tool_constants.py：工具层。TOOL_HTTP_* 是工具自己判断重试用的拷贝，TOOL_TIMEOUTS 等是工具运行参数。

禁止：
  ❌ 本文件引用 tool_constants.py 的任何内容
  ❌ 本文件的 SYS_HTTP_* 被工具层代码直接引用（工具层应引用 tool_constants.py 的 TOOL_HTTP_*）
"""

# ============================================================
# 1. HTTP 状态码与错误码
# ============================================================

HTTP_RATE_LIMIT = 429

RATE_LIMIT_STATUS_CODES = {HTTP_RATE_LIMIT, 1305}

# ============================================================
# 2. 重试与限流
# ============================================================

DEFAULT_MAX_STEPS = 100
MAX_CONSECUTIVE_CHUNKS = 5
MAX_CHUNKS_WITHOUT_PROMOTE = 50

# ============================================================
# 3. 网络与超时
# ============================================================

DEFAULT_LLM_TIMEOUT = 60
DEFAULT_READ_TIMEOUT = 60.0
DEFAULT_CONNECT_TIMEOUT = 30.0
DEFAULT_WRITE_TIMEOUT = 10.0
DEFAULT_POOL_TIMEOUT = 10.0

LLM_MAX_CONNECTIONS = 10
LLM_MAX_KEEPALIVE = 5
# NETWORK_TOOL_MAX_* 已迁移到 tool_constants.py (NETWORK_MAX_CONNECTIONS/NETWORK_MAX_KEEPALIVE)

# BROWSER_USER_AGENT 已迁移到 tool_constants.py → TOOL_BROWSER_UA

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

# ============================================================
# 4. 内容截断与字符限制
# ============================================================

MAX_CONTEXT_CHARS = 200000
TEMP_HISTORY_CHAR_LIMIT = 50000

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

# 全部 ERR_* 工具错误码已迁移到 tool_constants.py 第12节

# ============================================================
# 5. 会话与缓存(从 message_saver/display_name_cache 迁移)
# ============================================================

MAX_CACHE_SIZE = 1000

# ============================================================
# 10. SSE流超时(从 react_sse_wrapper 迁移)
# ============================================================

from datetime import timedelta
TASK_TIMEOUT = timedelta(hours=1)

# HITL超时(秒) — H-1修复 2026-06-25 小欧
HITL_TIMEOUT = 120


